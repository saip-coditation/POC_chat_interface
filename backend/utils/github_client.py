"""
GitHub API Client

Handles GitHub API interactions for data fetching.
Uses Personal Access Token (PAT) for authentication.
"""

import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def _get_headers(token: str) -> dict:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DataBridge-AI"
    }


def validate_token(token: str) -> dict:
    """
    Validate a GitHub Personal Access Token.
    
    Args:
        token: GitHub PAT
        
    Returns:
        dict with 'valid' boolean and user info if valid
    """
    try:
        response = requests.get(
            f"{GITHUB_API_BASE}/user",
            headers=_get_headers(token),
            timeout=10
        )
        
        if response.status_code == 200:
            user = response.json()
            return {
                'valid': True,
                'username': user.get('login'),
                'name': user.get('name') or user.get('login'),
                'avatar_url': user.get('avatar_url'),
                'public_repos': user.get('public_repos', 0),
                'private_repos': user.get('total_private_repos', 0)
            }
        elif response.status_code == 401:
            return {'valid': False, 'error': 'Invalid or expired token'}
        else:
            return {'valid': False, 'error': f'GitHub API error: {response.status_code}'}
            
    except requests.exceptions.Timeout:
        return {'valid': False, 'error': 'Connection timeout'}
    except Exception as e:
        logger.error(f"GitHub validation error: {e}")
        return {'valid': False, 'error': str(e)}


def fetch_repos(token: str, filters: dict = None) -> dict:
    """
    Fetch repositories for the authenticated user.
    
    Args:
        token: GitHub PAT
        filters: Optional filters (type: all/owner/member, sort, limit)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        params = {
            'per_page': min(filters.get('limit', 100), 100),
            'sort': filters.get('sort', 'updated'),
            'type': filters.get('type', 'all')
        }
        
        response = requests.get(
            f"{GITHUB_API_BASE}/user/repos",
            headers=_get_headers(token),
            params=params,
            timeout=15
        )
        
        if response.status_code != 200:
            return {'data': [], 'count': 0, 'error': f'API error: {response.status_code}'}
        
        repos = response.json()
        data = []
        
        for repo in repos:
            data.append({
                'id': repo['id'],
                'name': repo['name'],
                'full_name': repo['full_name'],
                'description': repo.get('description') or 'No description',
                'private': repo['private'],
                'language': repo.get('language') or 'Unknown',
                'stars': repo['stargazers_count'],
                'forks': repo['forks_count'],
                'open_issues': repo['open_issues_count'],
                'created_at': repo['created_at'],
                'updated_at': repo['updated_at'],
                'url': repo['html_url']
            })
        
        return {
            'data': data,
            'count': len(data)
        }
        
    except Exception as e:
        logger.error(f"GitHub fetch repos error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_repo_summary(token: str, owner: str, repo: str) -> dict:
    """
    Get detailed summary for a specific repository.
    
    Args:
        token: GitHub PAT
        owner: Repository owner
        repo: Repository name
        
    Returns:
        dict with repository details
    """
    try:
        headers = _get_headers(token)
        
        # Fetch repo details
        repo_response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
            headers=headers,
            timeout=10
        )
        
        if repo_response.status_code != 200:
            return {'error': f'Repository not found or access denied'}
        
        repo_data = repo_response.json()
        
        # Fetch languages
        lang_response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages",
            headers=headers,
            timeout=10
        )
        languages = lang_response.json() if lang_response.status_code == 200 else {}
        
        # Fetch contributors count
        contrib_response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contributors",
            headers=headers,
            params={'per_page': 1},
            timeout=10
        )
        # Get total from Link header if available
        contributors_count = 0
        if 'Link' in contrib_response.headers:
            # Parse last page from Link header
            links = contrib_response.headers['Link']
            if 'last' in links:
                import re
                match = re.search(r'page=(\d+)>; rel="last"', links)
                if match:
                    contributors_count = int(match.group(1))
        else:
            contributors_count = len(contrib_response.json()) if contrib_response.status_code == 200 else 0
        
        # Fetch recent commits count (last 30 days)
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=30)).isoformat() + 'Z'
        commits_response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
            headers=headers,
            params={'since': since, 'per_page': 100},
            timeout=10
        )
        recent_commits = len(commits_response.json()) if commits_response.status_code == 200 else 0
        
        return {
            'name': repo_data['name'],
            'full_name': repo_data['full_name'],
            'description': repo_data.get('description') or 'No description',
            'private': repo_data['private'],
            'default_branch': repo_data['default_branch'],
            'stars': repo_data['stargazers_count'],
            'forks': repo_data['forks_count'],
            'watchers': repo_data['watchers_count'],
            'open_issues': repo_data['open_issues_count'],
            'languages': languages,
            'primary_language': repo_data.get('language') or 'Unknown',
            'contributors_count': contributors_count,
            'recent_commits_30d': recent_commits,
            'size_kb': repo_data['size'],
            'created_at': repo_data['created_at'],
            'updated_at': repo_data['updated_at'],
            'pushed_at': repo_data['pushed_at'],
            'license': repo_data.get('license', {}).get('name') if repo_data.get('license') else 'No license',
            'url': repo_data['html_url']
        }
        
    except Exception as e:
        logger.error(f"GitHub fetch repo summary error: {e}")
        return {'error': str(e)}


def fetch_commits(token: str, owner: str, repo: str, filters: dict = None) -> dict:
    """
    Fetch commits for a repository.
    
    Args:
        token: GitHub PAT
        owner: Repository owner
        repo: Repository name
        filters: Optional filters (limit, since, until, author)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        params = {
            'per_page': min(filters.get('limit', 30), 100)
        }
        
        if filters.get('author'):
            params['author'] = filters['author']
        if filters.get('since'):
            params['since'] = filters['since']
        if filters.get('until'):
            params['until'] = filters['until']
        
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
            headers=_get_headers(token),
            params=params,
            timeout=15
        )
        
        if response.status_code != 200:
            return {'data': [], 'count': 0, 'error': f'API error: {response.status_code}'}
        
        commits = response.json()
        data = []
        
        for commit in commits:
            commit_data = commit.get('commit', {})
            author = commit_data.get('author', {})
            data.append({
                'sha': commit['sha'][:7],
                'message': commit_data.get('message', '').split('\n')[0][:100],  # First line, max 100 chars
                'author': author.get('name', 'Unknown'),
                'author_email': author.get('email', ''),
                'date': author.get('date', ''),
                'url': commit.get('html_url', '')
            })
        
        return {
            'data': data,
            'count': len(data),
            'repository': f"{owner}/{repo}"
        }
        
    except Exception as e:
        logger.error(f"GitHub fetch commits error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_pull_requests(token: str, owner: str, repo: str, filters: dict = None) -> dict:
    """
    Fetch pull requests for a repository.
    
    Args:
        token: GitHub PAT
        owner: Repository owner
        repo: Repository name
        filters: Optional filters (state: open/closed/all, limit)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        params = {
            'per_page': min(filters.get('limit', 30), 100),
            'state': filters.get('state', 'all'),
            'sort': 'updated',
            'direction': 'desc'
        }
        
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
            headers=_get_headers(token),
            params=params,
            timeout=15
        )
        
        if response.status_code != 200:
            return {'data': [], 'count': 0, 'error': f'API error: {response.status_code}'}
        
        prs = response.json()
        data = []
        
        for pr in prs:
            data.append({
                'number': pr['number'],
                'title': pr['title'][:100],
                'state': pr['state'],
                'merged': pr.get('merged_at') is not None,
                'author': pr['user']['login'],
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'merged_at': pr.get('merged_at'),
                'comments': pr.get('comments', 0),
                'url': pr['html_url']
            })
        
        # Count stats
        open_count = sum(1 for p in data if p['state'] == 'open')
        merged_count = sum(1 for p in data if p['merged'])
        closed_count = sum(1 for p in data if p['state'] == 'closed' and not p['merged'])
        
        return {
            'data': data,
            'count': len(data),
            'open': open_count,
            'merged': merged_count,
            'closed': closed_count,
            'repository': f"{owner}/{repo}"
        }
        
    except Exception as e:
        logger.error(f"GitHub fetch PRs error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}


def fetch_issues(token: str, owner: str, repo: str, filters: dict = None) -> dict:
    """
    Fetch issues for a repository.
    
    Args:
        token: GitHub PAT
        owner: Repository owner
        repo: Repository name
        filters: Optional filters (state: open/closed/all, limit, labels)
        
    Returns:
        dict with 'data' list and 'count'
    """
    filters = filters or {}
    
    try:
        params = {
            'per_page': min(filters.get('limit', 30), 100),
            'state': filters.get('state', 'all'),
            'sort': 'updated',
            'direction': 'desc'
        }
        
        if filters.get('labels'):
            params['labels'] = filters['labels']
        
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
            headers=_get_headers(token),
            params=params,
            timeout=15
        )
        
        if response.status_code != 200:
            return {'data': [], 'count': 0, 'error': f'API error: {response.status_code}'}
        
        issues = response.json()
        data = []
        
        # Filter out pull requests (GitHub API returns PRs in issues endpoint)
        for issue in issues:
            if 'pull_request' in issue:
                continue
                
            data.append({
                'number': issue['number'],
                'title': issue['title'][:100],
                'state': issue['state'],
                'author': issue['user']['login'],
                'labels': [l['name'] for l in issue.get('labels', [])],
                'comments': issue.get('comments', 0),
                'created_at': issue['created_at'],
                'updated_at': issue['updated_at'],
                'url': issue['html_url']
            })
        
        open_count = sum(1 for i in data if i['state'] == 'open')
        closed_count = sum(1 for i in data if i['state'] == 'closed')
        
        return {
            'data': data,
            'count': len(data),
            'open': open_count,
            'closed': closed_count,
            'repository': f"{owner}/{repo}"
        }
        
    except Exception as e:
        logger.error(f"GitHub fetch issues error: {e}")
        return {'data': [], 'count': 0, 'error': str(e)}
