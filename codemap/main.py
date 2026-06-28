"""
main.py
CodeMAP build pipeline entry point — build_codemap

Pipeline:
  Phase 1 Structure   : repo init, language detection, group/file/func parsing, callgraph
  Phase 2 Semantic    : function summary generation  (SA + LLM, parallelised)
  Phase 3 Description : file / group / repo description generation  (LLM)

Usage
-----
  python main.py /path/to/repo
  python main.py /path/to/repo --force
  python main.py /path/to/repo --repo-name my_project --db-path ./my.db
  python main.py /path/to/repo --step 9
  python main.py /path/to/repo --languages C C++
  python main.py /path/to/repo --no-desc
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from config import DB_PATH, DATA_DIR
from db.dao import init_db, RepoDB, FuncDB, FileDB

from analyzer.repo_analyzer import (
    init_repo,
    analyze_repo_language,
    analyze_repo_group,
    analyze_repo_grouplist_brief,
    analyze_repo_description,
)
from analyzer.group_analyzer import (
    analyze_group_file,
    analyze_group_filelist_brief,
    analyze_group_description,
)
from analyzer.file_analyzer import (
    analyze_file_language,
    analyze_file_func,
    analyze_file_funclist_brief,
    analyze_file_description,
)
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
from analyzer.func_analyzer import analyze_func_summary


# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

def _make_logger(log_dir: Optional[str] = None) -> tuple[logging.Logger, str]:
    """Create a logger writing DEBUG to file and INFO to stdout."""
    _log_dir = log_dir or os.path.join(_HERE, 'logs')
    os.makedirs(_log_dir, exist_ok=True)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(_log_dir, f'codemap_{ts}.log')

    logger = logging.getLogger(f'codemap_{ts}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-7s  %(message)s', datefmt='%H:%M:%S',
    ))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S'))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger, log_file


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def _enable_wal(db_path: str, logger: logging.Logger) -> None:
    """Enable SQLite WAL mode to prevent SQLITE_BUSY under concurrent writes."""
    try:
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
            conn.execute('PRAGMA synchronous=NORMAL')
        logger.debug(f'[WAL] journal_mode={mode}')
    except Exception as e:
        logger.warning(f'[WAL] failed (non-fatal): {e}')


class _Timer:
    """Context manager that logs a label and elapsed time."""

    def __init__(self, label: str, logger: logging.Logger):
        self._label  = label
        self._t0     = 0.0
        self._logger = logger

    def __enter__(self):
        self._t0 = time.time()
        self._logger.info(f'▶ {self._label}')
        return self

    def __exit__(self, exc_type, *_):
        elapsed    = time.time() - self._t0
        mins, secs = divmod(int(elapsed), 60)
        duration   = f'{mins}m {secs}s' if mins else f'{secs}s'
        icon       = '✓' if exc_type is None else '✗'
        self._logger.info(f'◀ {icon} {self._label}  [{duration}]')


def _find_repo_id(repo_name: str, repo_path: str, db_path: str) -> Optional[int]:
    """Look up an existing repo ID: by name first, then by absolute path."""
    rec = RepoDB.get_by_name(repo_name, db_path=db_path)
    if rec:
        return rec['id']
    abs_path = os.path.abspath(repo_path)
    for r in RepoDB.list_all(db_path=db_path):
        if os.path.abspath(r.get('path', '')) == abs_path:
            return r['id']
    return None


# ------------------------------------------------------------------
# build_codemap
# ------------------------------------------------------------------

def build_codemap(
    repo_path: str,
    repo_name: Optional[str] = None,
    db_path: Optional[str] = None,
    force: bool = False,
    start_step: int = 1,
    languages: Optional[list[str]] = None,
    skip_if_exists: bool = True,
    max_func_summary_workers: int = 30,
    no_desc: bool = False,
    log_dir: Optional[str] = None,
) -> dict:
    """
    Build a CodeMAP knowledge base for the given repository.

    Pipeline
    --------
    Phase 1 Structure Analysis
        Repo init → language detection → group/file/func extraction → callgraph.
    Phase 2 Semantic Analysis  (SA + LLM, parallelised)
        Function precondition / postcondition / exception / description,
        dispatched concurrently via ThreadPoolExecutor.
    Phase 3 Description Generation  (LLM)
        File / group / repo level summaries.  Skippable via no_desc=True.

    Parameters
    ----------
    repo_path : str
        Local path to the repository.
    repo_name : str | None
        Repository name; defaults to the last path component.
    db_path : str | None
        SQLite database path; defaults to config.DB_PATH.
    force : bool
        Drop existing repo data and rebuild from scratch.
    languages : list[str] | None
        Language whitelist for function analysis; None = all.
    skip_if_exists : bool
        Skip entities that already have data in the DB.
    max_func_summary_workers : int
        Thread-pool size for Phase 2 parallel LLM calls (default 30).
    no_desc : bool
        Skip Phase 3 entirely.
    log_dir : str | None
        Log output directory; defaults to <project_root>/logs/.

    Returns
    -------
    dict
        Build summary: repo_id, repo_name, db_path, log_file,
        total_elapsed, and per-step statistics.
    """
    abs_repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_repo_path):
        raise FileNotFoundError(f'repo path not found or not a directory: {abs_repo_path}')
    if not (1 <= start_step <= 18):
        raise ValueError(f'start_step={start_step} out of range [1, 18]')

    _db      = db_path or DB_PATH
    _name    = repo_name or os.path.basename(abs_repo_path.rstrip(os.sep))
    summary: dict = {}

    _log, log_file = _make_logger(log_dir)

    _log.info('=' * 70)
    _log.info('CodeMAP build started')
    _log.info(f'  repo_path     : {abs_repo_path}')
    _log.info(f'  repo_name     : {_name}')
    _log.info(f'  db_path       : {_db}')
    _log.info(f'  log_file      : {log_file}')
    _log.info(f'  force         : {force}')
    _log.info(f'  start_step    : {start_step}')
    _log.info(f'  languages     : {languages or "all"}')
    _log.info(f'  skip_exists   : {skip_if_exists}')
    _log.info(f'  no_desc       : {no_desc}')
    _log.info(f'  func_workers  : {max_func_summary_workers}')
    _log.info('=' * 70)

    total_t0 = time.time()

    os.makedirs(os.path.dirname(os.path.abspath(_db)), exist_ok=True)
    init_db(_db)
    _enable_wal(_db, _log)

    # ══════════════════════════════════════════════════════════════
    # Phase 1 — Structure Analysis  (Steps 1–8)
    # ══════════════════════════════════════════════════════════════

    # Step 1: init_repo
    repo_id: Optional[int] = None
    if start_step <= 1:
        with _Timer('Step 1   init_repo', _log):
            repo_id = init_repo(
                repo_path=abs_repo_path, repo_name=_name, db_path=_db, force=force,
            )
        _log.info(f'  repo_id = {repo_id}')
        summary['step1'] = {'repo_id': repo_id}
    else:
        repo_id = _find_repo_id(_name, abs_repo_path, _db)
        if repo_id is None:
            raise ValueError(
                f'start_step={start_step} but repo "{_name}" not found in DB. '
                'Run from step 1 first.'
            )
        _log.info(f'Step 1 skipped — repo_id={repo_id}')
        summary['step1'] = {'repo_id': repo_id, 'skipped': True}

    # Step 2: analyze_repo_language
    if start_step <= 2:
        with _Timer('Step 2   analyze_repo_language', _log):
            lang_r = analyze_repo_language(repo_id, db_path=_db)
        _log.info(f'  main language: {lang_r.get("main", "Unknown")}')
        summary['step2'] = {'main_language': lang_r.get('main')}
    else:
        _log.info('Step 2 skipped')
        summary['step2'] = {'skipped': True}

    # Step 3: analyze_repo_group  [LLM]
    if start_step <= 3:
        with _Timer('Step 3   analyze_repo_group  [LLM]', _log):
            group_r = analyze_repo_group(repo_id, db_path=_db, force=force)
        _log.info(f'  groups: {len(group_r)}')
        summary['step3'] = {'group_count': len(group_r)}
    else:
        _log.info('Step 3 skipped')
        summary['step3'] = {'skipped': True}

    # Step 4: analyze_group_file
    if start_step <= 4:
        with _Timer('Step 4   analyze_group_file', _log):
            file_r = analyze_group_file(repo_id, db_path=_db, force=force)
        total_files = sum(len(v) for v in file_r.values())
        _log.info(f'  files: {total_files}')
        summary['step4'] = {'file_count': total_files}
    else:
        _log.info('Step 4 skipped')
        summary['step4'] = {'skipped': True}

    # Step 5: analyze_file_language
    if start_step <= 5:
        with _Timer('Step 5   analyze_file_language', _log):
            lang_map = analyze_file_language(repo_id, db_path=_db)
        _log.info(f'  detected files: {len(lang_map)}')
        summary['step5'] = {'detected_files': len(lang_map)}
    else:
        _log.info('Step 5 skipped')
        summary['step5'] = {'skipped': True}

    # Step 6: analyze_file_func
    if start_step <= 6:
        with _Timer('Step 6   analyze_file_func', _log):
            func_r = analyze_file_func(
                repo_id, db_path=_db, force=force, languages=languages,
            )
        total_funcs = sum(len(v) for v in func_r.values())
        _log.info(f'  functions: {total_funcs}')
        summary['step6'] = {'func_count': total_funcs}
    else:
        _log.info('Step 6 skipped')
        summary['step6'] = {'skipped': True}

    # Step 7: build_callgraph
    if start_step <= 7:
        with _Timer('Step 7   build_callgraph', _log):
            cg_path = build_callgraph(repo_id, db_path=_db, force=force)
        _log.info(f'  callgraph: {cg_path}')
        summary['step7'] = {'callgraph_path': cg_path}
    else:
        # Reconstruct expected callgraph path for downstream steps
        repo_rec = RepoDB.get_by_id(repo_id, db_path=_db)
        cg_path  = os.path.join(
            DATA_DIR, 'callgraph',
            f"{repo_rec['name']}_callgraph.json" if repo_rec else '',
        )
        _log.info(f'Step 7 skipped — cached path: {cg_path}')
        summary['step7'] = {'skipped': True, 'callgraph_path': cg_path}

    # Step 8: analyze_func_callgraph
    if start_step <= 8:
        with _Timer('Step 8   analyze_func_callgraph', _log):
            cg_r = analyze_func_callgraph(
                repo_id,
                db_path        = _db,
                callgraph_path = cg_path if os.path.isfile(cg_path) else None,
            )
        _log.info(f'  funcs written: {len(cg_r)}')
        summary['step8'] = {'func_count': len(cg_r)}
    else:
        _log.info('Step 8 skipped')
        summary['step8'] = {'skipped': True}

    # ══════════════════════════════════════════════════════════════
    # Phase 2 — Semantic Analysis  (Steps 9–12)
    # analyze_func_summary is called once per function in a thread
    # pool of size max_func_summary_workers (default 30).
    # Requires analyze_func_summary to accept a func_id parameter.
    # SQLite WAL mode (enabled above) serialises concurrent writes.
    # ══════════════════════════════════════════════════════════════
    if start_step <= 9:
        with _Timer('Phase 2  analyze_func_summary  [SA+LLM, parallel]', _log):

            all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
            if languages:
                all_funcs = [f for f in all_funcs if f.get('language') in languages]
            func_ids = [f['id'] for f in all_funcs]
            total    = len(func_ids)
            _log.info(f'  functions to process : {total}')
            _log.info(f'  parallel workers     : {max_func_summary_workers}')

            summary_r = {}
            completed = 0
            failed    = 0

            def _run_one(fid: int):
                """Analyse a single function; called from worker threads."""
                return fid, analyze_func_summary(
                    func_id        = fid,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )

            with ThreadPoolExecutor(max_workers=max_func_summary_workers) as pool:
                futures = {pool.submit(_run_one, fid): fid for fid in func_ids}
                for fut in as_completed(futures):
                    fid = futures[fut]
                    try:
                        _, result = fut.result()
                        summary_r[fid] = result
                    except Exception as exc:
                        _log.warning(f'  func_id={fid} error: {exc}')
                        summary_r[fid] = None
                        failed += 1
                    completed += 1
                    if completed % 100 == 0 or completed == total:
                        _log.info(f'  progress: {completed}/{total}  (errors={failed})')

        ne = sum(1 for v in summary_r.values() if v)
        _log.info(f'  done: {ne}/{total} with data  ({failed} errors)')
        for s in range(9, 13):
            summary[f'step{s}'] = {'total': total, 'nonempty': ne, 'failed': failed}
    else:
        _log.info('Phase 2 skipped')
        for s in range(9, 13):
            summary[f'step{s}'] = {'skipped': True}

    # ══════════════════════════════════════════════════════════════
    # Phase 3 — Description Generation  (Steps 13–18)
    # ══════════════════════════════════════════════════════════════
    if no_desc:
        _log.info('--no-desc: skipping Phase 3 (Steps 13–18)')
        for s in range(13, 19):
            summary[f'step{s}'] = {'skipped': True, 'reason': 'no_desc'}

    else:
        # Step 13: analyze_file_funclist_brief  [LLM batch]
        if start_step <= 13:
            with _Timer('Step 13  analyze_file_funclist_brief', _log):
                fl_brief = analyze_file_funclist_brief(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            _log.info(f'  files processed: {len(fl_brief)}')
            summary['step13'] = {'file_count': len(fl_brief)}
        else:
            _log.info('Step 13 skipped')
            summary['step13'] = {'skipped': True}

        # Step 14: analyze_file_description  [LLM]
        if start_step <= 14:
            with _Timer('Step 14  analyze_file_description', _log):
                file_desc = analyze_file_description(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            ne = sum(1 for v in file_desc.values() if v)
            _log.info(f'  file descriptions: {ne}/{len(file_desc)}')
            summary['step14'] = {'total': len(file_desc), 'nonempty': ne}
        else:
            _log.info('Step 14 skipped')
            summary['step14'] = {'skipped': True}

        # Step 15: analyze_group_filelist_brief  [LLM batch]
        if start_step <= 15:
            with _Timer('Step 15  analyze_group_filelist_brief', _log):
                al_brief = analyze_group_filelist_brief(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            _log.info(f'  groups processed: {len(al_brief)}')
            summary['step15'] = {'group_count': len(al_brief)}
        else:
            _log.info('Step 15 skipped')
            summary['step15'] = {'skipped': True}

        # Step 16: analyze_group_description  [LLM]
        if start_step <= 16:
            with _Timer('Step 16  analyze_group_description', _log):
                group_desc = analyze_group_description(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            ne = sum(1 for v in group_desc.values() if v)
            _log.info(f'  group descriptions: {ne}/{len(group_desc)}')
            summary['step16'] = {'total': len(group_desc), 'nonempty': ne}
        else:
            _log.info('Step 16 skipped')
            summary['step16'] = {'skipped': True}

        # Step 17: analyze_repo_grouplist_brief  [LLM batch]
        if start_step <= 17:
            with _Timer('Step 17  analyze_repo_grouplist_brief', _log):
                grouplist = analyze_repo_grouplist_brief(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            _log.info(f'  grouplist entries: {len(grouplist)}')
            summary['step17'] = {'group_count': len(grouplist)}
        else:
            _log.info('Step 17 skipped')
            summary['step17'] = {'skipped': True}

        # Step 18: analyze_repo_description  [LLM]
        if start_step <= 18:
            with _Timer('Step 18  analyze_repo_description', _log):
                repo_desc = analyze_repo_description(
                    repo_id=repo_id, db_path=_db, skip_if_exists=skip_if_exists,
                )
            _log.info(f'  repo description: {len(repo_desc)} chars')
            summary['step18'] = {'desc_chars': len(repo_desc)}
        else:
            _log.info('Step 18 skipped')
            summary['step18'] = {'skipped': True}

    # ── Final report ───────────────────────────────────────────────────────
    total_elapsed = time.time() - total_t0
    mins, secs    = divmod(int(total_elapsed), 60)

    _STEP_LABELS = {
        1:  'init_repo',                2:  'analyze_repo_language',
        3:  'analyze_repo_group',        4:  'analyze_group_file',
        5:  'analyze_file_language',    6:  'analyze_file_func',
        7:  'build_callgraph',          8:  'analyze_func_callgraph',
        9:  'func_precondition',        10: 'func_postcondition',
        11: 'func_exception',           12: 'func_description',
        13: 'file_funclist_brief',      14: 'file_description',
        15: 'group_filelist_brief',      16: 'group_description',
        17: 'repo_grouplist_brief',      18: 'repo_description',
    }

    _log.info('')
    _log.info('=' * 70)
    _log.info('CodeMAP build complete  ✓')
    _log.info(f'  repo    : {_name}  (id={repo_id})')
    _log.info(f'  db      : {_db}')
    _log.info(f'  log     : {log_file}')
    _log.info(f'  elapsed : {mins}m {secs}s  ({total_elapsed:.0f}s)')
    _log.info('  ' + '─' * 66)
    for num, label in _STEP_LABELS.items():
        info = summary.get(f'step{num}', {})
        if info.get('skipped'):
            reason = info.get('reason', '')
            status = f'[skipped{" — " + reason if reason else ""}]'
        else:
            parts = [
                f'{k}={v}'
                for k, v in info.items()
                if k not in ('skipped', 'reason', 'callgraph_path') and v is not None
            ]
            status = '  '.join(parts) if parts else '✓'
        _log.info(f'  Step {num:2d}  {label:<30s}  {status}')
    _log.info('=' * 70)

    summary.update({
        'repo_id':       repo_id,
        'repo_name':     _name,
        'db_path':       _db,
        'log_file':      log_file,
        'total_elapsed': total_elapsed,
    })
    return summary


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and invoke build_codemap."""
    parser = argparse.ArgumentParser(
        prog            = 'codemap',
        description     = 'CodeMAP — structured knowledge base builder for code repositories',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog          = """
Examples:
  python main.py /path/to/repo                         # full analysis
  python main.py /path/to/repo --force                 # force rebuild
  python main.py /path/to/repo --step 9                # resume from Phase 2
  python main.py /path/to/repo --repo-name my_proj --db-path ./my.db
  python main.py /path/to/repo --languages C C++       # C/C++ only
  python main.py /path/to/repo --no-desc               # skip Phase 3
  python main.py /path/to/repo --step 9 --no-skip      # re-analyse all funcs
  python main.py /path/to/repo --func-workers 50       # raise Phase 2 concurrency
        """.strip(),
    )

    parser.add_argument('repo_path',
                        help='path to the local repository')
    parser.add_argument('--repo-name', '-n', dest='repo_name', default=None, metavar='NAME',
                        help='repository name (default: last path component)')
    parser.add_argument('--db-path', '-d', dest='db_path', default=None, metavar='PATH',
                        help=f'SQLite database path (default: {DB_PATH})')
    parser.add_argument('--force', '-f', action='store_true', default=False,
                        help='drop existing repo data and rebuild from scratch')
    parser.add_argument('--step', '-s', type=int, default=1, choices=range(1, 19), metavar='N',
                        help='resume from step N (1–18, default 1)')
    parser.add_argument('--languages', '-l', nargs='+', default=None, metavar='LANG',
                        help='language whitelist for func analysis (e.g. C C++); default: all')
    parser.add_argument('--no-desc', action='store_true', default=False,
                        help='skip Phase 3 (Steps 13–18): no description generation')
    parser.add_argument('--no-skip', action='store_true', default=False,
                        help='re-analyse all entities even if they already exist in the DB')
    parser.add_argument('--func-workers', type=int, default=30, metavar='N',
                        help='thread-pool size for Phase 2 func summary (default: 30)')
    parser.add_argument('--log-dir', dest='log_dir', default=None, metavar='DIR',
                        help='log output directory (default: <project_root>/logs/)')

    args = parser.parse_args()

    try:
        build_codemap(
            repo_path                = args.repo_path,
            repo_name                = args.repo_name,
            db_path                  = args.db_path,
            force                    = args.force,
            start_step               = args.step,
            languages                = args.languages,
            skip_if_exists           = not args.no_skip,
            max_func_summary_workers = args.func_workers,
            no_desc                  = args.no_desc,
            log_dir                  = args.log_dir,
        )
        sys.exit(0)

    except FileNotFoundError as e:
        print(f'[error] {e}', file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        print(f'[error] {e}', file=sys.stderr)
        sys.exit(2)

    except KeyboardInterrupt:
        print(
            '\n[interrupted] Build stopped by user. '
            'Completed data is persisted; resume with --step N.',
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as e:
        print(f'[fatal] {e}', file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()