import asyncio
import base64
import logging
from datetime import datetime

from github import Github, GithubException, UnknownObjectException

logger = logging.getLogger(__name__)


def _client(token: str) -> Github:
    return Github(token)


# ── Search ───────────────────────────────────────────────────────────────────

def _search_repos_sync(token: str, query: str, max_results: int) -> list[dict]:
    g = _client(token)
    repos = g.search_repositories(query=query, sort="stars")
    results = []
    for r in repos[:max_results]:
        results.append({
            "full_name": r.full_name,
            "description": r.description or "",
            "stars": r.stargazers_count,
            "language": r.language or "",
            "url": r.html_url,
            "updated": r.updated_at.strftime("%Y-%m-%d") if r.updated_at else "",
        })
    return results


def _search_code_sync(token: str, query: str, repo_filter: str | None, max_results: int) -> list[dict]:
    g = _client(token)
    q = query
    if repo_filter:
        q += f" repo:{repo_filter}"
    results_raw = g.search_code(query=q)
    results = []
    for item in results_raw[:max_results]:
        results.append({
            "repo": item.repository.full_name,
            "path": item.path,
            "url": item.html_url,
            "sha": item.sha[:7],
        })
    return results


async def search_repos(token: str, query: str, max_results: int = 5) -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _search_repos_sync, token, query, max_results)


async def search_code(token: str, query: str, repo_filter: str | None = None, max_results: int = 5) -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _search_code_sync, token, query, repo_filter, max_results)


# ── Read ─────────────────────────────────────────────────────────────────────

def _get_repo_info_sync(token: str, full_name: str) -> dict | None:
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        branches = [b.name for b in r.get_branches()][:5]
        recent_commits = []
        for c in r.get_commits()[:5]:
            recent_commits.append({
                "sha": c.sha[:7],
                "message": c.commit.message.split("\n")[0],
                "author": c.commit.author.name,
                "date": c.commit.author.date.strftime("%Y-%m-%d"),
            })
        open_prs = r.get_pulls(state="open").totalCount
        open_issues = r.get_issues(state="open").totalCount
        return {
            "full_name": r.full_name,
            "description": r.description or "",
            "stars": r.stargazers_count,
            "language": r.language or "",
            "default_branch": r.default_branch,
            "branches": branches,
            "open_prs": open_prs,
            "open_issues": open_issues,
            "url": r.html_url,
            "recent_commits": recent_commits,
        }
    except UnknownObjectException:
        return None
    except Exception as e:
        logger.error(f"get_repo_info failed: {e}")
        return None


def _read_file_sync(token: str, full_name: str, path: str, ref: str) -> dict | None:
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        contents = r.get_contents(path, ref=ref)
        if isinstance(contents, list):
            return {"error": "Path is a directory", "items": [c.path for c in contents]}
        decoded = base64.b64decode(contents.content).decode("utf-8", errors="replace")
        return {
            "path": contents.path,
            "sha": contents.sha,
            "size": contents.size,
            "content": decoded,
            "url": contents.html_url,
        }
    except UnknownObjectException:
        return None
    except Exception as e:
        logger.error(f"read_file failed: {e}")
        return None


def _list_prs_sync(token: str, full_name: str, state: str) -> list[dict]:
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "state": pr.state,
                "branch": pr.head.ref,
                "url": pr.html_url,
                "created": pr.created_at.strftime("%Y-%m-%d"),
            }
            for pr in r.get_pulls(state=state)[:10]
        ]
    except Exception as e:
        logger.error(f"list_prs failed: {e}")
        return []


def _list_issues_sync(token: str, full_name: str, state: str) -> list[dict]:
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        return [
            {
                "number": issue.number,
                "title": issue.title,
                "author": issue.user.login,
                "state": issue.state,
                "url": issue.html_url,
                "created": issue.created_at.strftime("%Y-%m-%d"),
            }
            for issue in r.get_issues(state=state)[:10]
            if issue.pull_request is None
        ]
    except Exception as e:
        logger.error(f"list_issues failed: {e}")
        return []


async def get_repo_info(token: str, full_name: str) -> dict | None:
    return await asyncio.get_event_loop().run_in_executor(None, _get_repo_info_sync, token, full_name)


async def read_file(token: str, full_name: str, path: str, ref: str = "main") -> dict | None:
    return await asyncio.get_event_loop().run_in_executor(None, _read_file_sync, token, full_name, path, ref)


async def list_prs(token: str, full_name: str, state: str = "open") -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _list_prs_sync, token, full_name, state)


async def list_issues(token: str, full_name: str, state: str = "open") -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _list_issues_sync, token, full_name, state)


# ── Write ────────────────────────────────────────────────────────────────────

def _edit_file_pr_sync(
    token: str, full_name: str, path: str, new_content: str,
    branch_name: str, commit_msg: str, pr_title: str, pr_body: str
) -> dict:
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        default_branch = r.default_branch

        # Create branch from default
        ref = r.get_git_ref(f"heads/{default_branch}")
        try:
            r.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
        except GithubException as e:
            if e.status == 422:
                # Branch already exists, update it
                existing_ref = r.get_git_ref(f"heads/{branch_name}")
                existing_ref.edit(ref.object.sha, force=True)
            else:
                raise

        # Get current file SHA if it exists (needed for update)
        file_sha = None
        try:
            existing = r.get_contents(path, ref=branch_name)
            if not isinstance(existing, list):
                file_sha = existing.sha
        except UnknownObjectException:
            pass

        # Commit file
        if file_sha:
            r.update_file(path, commit_msg, new_content, file_sha, branch=branch_name)
        else:
            r.create_file(path, commit_msg, new_content, branch=branch_name)

        # Create PR
        pr = r.create_pull(
            title=pr_title,
            body=pr_body or f"Automatisch erstellt von Jarvis\n\n{commit_msg}",
            head=branch_name,
            base=default_branch,
        )
        return {"success": True, "pr_url": pr.html_url, "pr_number": pr.number, "branch": branch_name}

    except Exception as e:
        logger.error(f"edit_file_pr failed: {e}")
        return {"success": False, "error": str(e)}


def _push_direct_sync(
    token: str, full_name: str, path: str, new_content: str,
    commit_msg: str, branch: str
) -> dict:
    """Push directly to a branch (no PR)."""
    try:
        g = _client(token)
        r = g.get_repo(full_name)
        file_sha = None
        try:
            existing = r.get_contents(path, ref=branch)
            if not isinstance(existing, list):
                file_sha = existing.sha
        except UnknownObjectException:
            pass

        if file_sha:
            result = r.update_file(path, commit_msg, new_content, file_sha, branch=branch)
        else:
            result = r.create_file(path, commit_msg, new_content, branch=branch)

        sha = result["commit"].sha[:7]
        return {"success": True, "sha": sha, "url": f"https://github.com/{full_name}/commit/{sha}"}
    except Exception as e:
        logger.error(f"push_direct failed: {e}")
        return {"success": False, "error": str(e)}


async def edit_file_pr(
    token: str, full_name: str, path: str, new_content: str,
    branch_name: str, commit_msg: str, pr_title: str, pr_body: str = ""
) -> dict:
    return await asyncio.get_event_loop().run_in_executor(
        None, _edit_file_pr_sync, token, full_name, path, new_content, branch_name, commit_msg, pr_title, pr_body
    )


async def push_direct(
    token: str, full_name: str, path: str, new_content: str,
    commit_msg: str, branch: str = "main"
) -> dict:
    return await asyncio.get_event_loop().run_in_executor(
        None, _push_direct_sync, token, full_name, path, new_content, commit_msg, branch
    )


# ── Formatters ───────────────────────────────────────────────────────────────

def format_repo_info(data: dict) -> str:
    lines = [
        f"📦 *{data['full_name']}*",
        f"_{data['description']}_" if data['description'] else "",
        f"",
        f"⭐ {data['stars']} | 💻 {data['language']} | 🌿 `{data['default_branch']}`",
        f"📬 {data['open_prs']} offene PRs | 🐛 {data['open_issues']} Issues",
        f"🌿 Branches: {', '.join(f'`{b}`' for b in data['branches'])}",
        f"",
        f"*Letzte Commits:*",
    ]
    for c in data['recent_commits']:
        lines.append(f"• `{c['sha']}` {c['message'][:60]} – {c['author']} ({c['date']})")
    lines.append(f"\n🔗 {data['url']}")
    return "\n".join(filter(lambda x: x is not None, lines))


def format_search_repos(results: list[dict]) -> str:
    if not results:
        return "❌ Keine Repos gefunden."
    lines = ["🔍 *GitHub Repos:*\n"]
    for r in results:
        lang = f" · {r['language']}" if r['language'] else ""
        lines.append(f"📦 *{r['full_name']}*{lang} ⭐{r['stars']}\n_{r['description'][:80]}_\n🔗 {r['url']}\n")
    return "\n".join(lines)


def format_prs(prs: list[dict], repo: str) -> str:
    if not prs:
        return f"✅ Keine offenen PRs in `{repo}`."
    lines = [f"📬 *Pull Requests – {repo}:*\n"]
    for pr in prs:
        lines.append(f"#{pr['number']} *{pr['title']}*\n🌿 `{pr['branch']}` | @{pr['author']} | {pr['created']}\n🔗 {pr['url']}\n")
    return "\n".join(lines)


def format_issues(issues: list[dict], repo: str) -> str:
    if not issues:
        return f"✅ Keine offenen Issues in `{repo}`."
    lines = [f"🐛 *Issues – {repo}:*\n"]
    for i in issues:
        lines.append(f"#{i['number']} *{i['title']}* | @{i['author']} | {i['created']}\n🔗 {i['url']}\n")
    return "\n".join(lines)
