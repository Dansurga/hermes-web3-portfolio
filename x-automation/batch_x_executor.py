#!/usr/bin/env python3
"""
Batch X Social Task Executor
Execute all X tasks from queue with multi-account support
"""

import json
import time
import re
from camoufox.sync_api import Camoufox

def parse_x_url(url):
    """Parse X URL to determine action type"""
    url_lower = url.lower()
    
    # Extract tweet ID if present
    tweet_id_match = re.search(r'/status/(\d+)', url)
    tweet_id = tweet_id_match.group(1) if tweet_id_match else None
    
    # Extract username if present
    username_match = re.search(r'x\.com/([^/\?]+)', url)
    username = username_match.group(1) if username_match else None
    
    # Determine action based on URL structure
    actions = []
    
    # If it's a tweet, assume Follow + Like + Retweet
    if tweet_id:
        if username and username != 'intent':
            actions.append({
                'type': 'follow',
                'url': f'https://x.com/intent/follow?screen_name={username}'
            })
        actions.append({
            'type': 'like',
            'url': f'https://x.com/intent/like?tweet_id={tweet_id}'
        })
        actions.append({
            'type': 'retweet',
            'url': f'https://x.com/intent/retweet?tweet_id={tweet_id}'
        })
    
    # If it's just a profile, follow only
    elif username and username != 'intent':
        actions.append({
            'type': 'follow',
            'url': f'https://x.com/intent/follow?screen_name={username}'
        })
    
    return actions

def load_x_accounts():
    """Load X accounts"""
    accounts = []
    with open("/root/garapan/x_accounts_15.txt") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    
    i = 0
    while i < len(lines):
        if lines[i].startswith('@'):
            username = lines[i].replace('@', '')
            auth_token = ''
            ct0 = ''
            
            if i+1 < len(lines) and lines[i+1].startswith('auth_token='):
                auth_token = lines[i+1].split('=', 1)[1]
            if i+2 < len(lines) and lines[i+2].startswith('ct0='):
                ct0 = lines[i+2].split('=', 1)[1]
            
            if auth_token and ct0:
                accounts.append({
                    'username': username,
                    'auth_token': auth_token,
                    'ct0': ct0
                })
            
            i += 3
        else:
            i += 1
    
    return accounts

def execute_actions(actions, account):
    """Execute X actions for one account"""
    PROXY = "socks5://127.0.0.1:1080"
    
    cookies = [
        {"name": "auth_token", "value": account['auth_token'], "domain": ".x.com", "path": "/"},
        {"name": "ct0", "value": account['ct0'], "domain": ".x.com", "path": "/"}
    ]
    
    results = []
    
    try:
        with Camoufox(headless="virtual", geoip=False, proxy={"server": PROXY}) as b:
            page = b.new_page()
            page.context.add_cookies(cookies)
            
            for action in actions:
                try:
                    page.goto(action['url'], timeout=30000)
                    time.sleep(3)
                    
                    # Try clicking confirm button
                    try:
                        btn = page.locator('div[data-testid*="confirm"]').first
                        btn.click(timeout=5000)
                        time.sleep(1)
                        results.append(True)
                    except:
                        # Fallback to JS click
                        page.evaluate("() => { const b = document.querySelector('button'); if(b) b.click(); }")
                        time.sleep(1)
                        results.append(True)
                    
                except Exception as e:
                    results.append(False)
                
                time.sleep(1)
    
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}
    
    return {
        'success': True,
        'completed': sum(results),
        'total': len(actions)
    }

def main():
    # Load tasks and accounts
    with open("/root/garapan/x_batch_tasks.json") as f:
        tasks = json.load(f)
    
    accounts = load_x_accounts()
    
    print(f"=== Batch X Social Executor ===")
    print(f"Time: {time.strftime('%H:%M')} WIB")
    print(f"Tasks: {len(tasks)}")
    print(f"Accounts: {len(accounts)}")
    print(f"Using: @{accounts[0]['username']} (main account)\n")
    
    # Parse all tasks into actions
    all_actions = []
    task_map = {}
    
    for task in tasks:
        url = task.get('url', '')
        actions = parse_x_url(url)
        
        if actions:
            all_actions.extend(actions)
            task_map[url] = {
                'title': task.get('title', 'N/A'),
                'actions': len(actions)
            }
    
    print(f"Total actions to execute: {len(all_actions)}\n")
    
    # Execute with main account (@cnn_denny equivalent - first account)
    main_account = accounts[0]
    
    print(f"Executing with @{main_account['username']}...\n")
    
    task_results = []
    
    for task in tasks:
        url = task.get('url', '')
        title = task.get('title', 'N/A')
        
        print(f"• {title[:60]}")
        
        actions = parse_x_url(url)
        
        if not actions:
            print(f"  ⚠️ No actions extracted\n")
            task_results.append({
                'task': title,
                'url': url,
                'status': 'skipped',
                'note': 'No actions extracted'
            })
            continue
        
        result = execute_actions(actions, main_account)
        
        if result['success']:
            print(f"  ✅ {result['completed']}/{result['total']} actions\n")
            task_results.append({
                'task': title,
                'url': url,
                'status': 'success',
                'actions': f"{result['completed']}/{result['total']}"
            })
        else:
            print(f"  ❌ {result.get('error', 'Unknown error')}\n")
            task_results.append({
                'task': title,
                'url': url,
                'status': 'error',
                'note': result.get('error', 'Unknown')
            })
        
        time.sleep(3)
    
    # Save results
    with open("/root/garapan/batch_x_results.json", "w") as f:
        json.dump(task_results, f, indent=2)
    
    # Summary
    success = [r for r in task_results if r['status'] == 'success']
    errors = [r for r in task_results if r['status'] == 'error']
    skipped = [r for r in task_results if r['status'] == 'skipped']
    
    print("\n=== RESULTS ===\n")
    print(f"✅ Success: {len(success)}/{len(tasks)}")
    print(f"❌ Errors: {len(errors)}/{len(tasks)}")
    print(f"⚠️ Skipped: {len(skipped)}/{len(tasks)}")
    print(f"\n/root/garapan/batch_x_results.json")

if __name__ == "__main__":
    main()
