"""Deploy 6 fixed actors to Apify via API push."""
import subprocess, sys, os

actors = [
    'linkedin-lead-scraper',
    'twitter-lead-scraper',
    'quora-lead-scraper',
    'upwork-lead-scraper',
    'craigslist-lead-scraper',
    'indiehackers-lead-scraper',
]

base_dir = r'c:\Users\usman\Music\lead-generation\services\apify-actors'

for actor in actors:
    actor_dir = os.path.join(base_dir, actor)
    print(f'\n=== Deploying {actor} ===')
    result = subprocess.run(
        ['apify', 'push'],
        cwd=actor_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        # Get last few lines of stdout
        lines = result.stdout.strip().split('\n')
        for line in lines[-5:]:
            print(f'  {line}')
        print(f'  ✅ SUCCESS')
    else:
        print(f'  ❌ FAILED (exit {result.returncode})')
        stderr_lines = result.stderr.strip().split('\n')
        for line in stderr_lines[-10:]:
            print(f'  ERR: {line}')

print('\nDone deploying all actors!')
