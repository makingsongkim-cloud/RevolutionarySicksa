import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
project_root = os.getenv("PROJECT_ROOT")
if project_root:
    sys.path.append(project_root)
else:
    current_file = Path(__file__).resolve()
    repo_root = None
    for parent in current_file.parents:
        if (parent / ".git").exists():
            repo_root = parent
            break
    if repo_root is None:
        repo_root = current_file.parent
    sys.path.append(str(repo_root))

try:
    from lunch_data import MENUS
    from recommender import LunchRecommender
except ImportError:
    # If standard import fails, try relative import assuming script is in project root
    sys.path.append(os.getcwd())
    from lunch_data import MENUS
    from recommender import LunchRecommender

def verify_tag_filtering():
    print("=== Tag Filtering Verification ===")
    r = LunchRecommender()
    
    # Test Case 1: Filter by 'soup'
    print("\nTest 1: Filter by tag=['soup']")
    result = r.recommend(tag_filters=['soup'])
    
    if result:
        tags = result.get('tags', [])
        print(f"Recommended: {result['name']} (Tags: {tags})")
        if 'soup' in tags:
            print("✅ PASS: Recommendation has 'soup' tag.")
        else:
            print(f"❌ FAIL: Recommendation {result['name']} does NOT have 'soup' tag.")
    else:
        print("❌ FAIL: No recommendation returned for soup.")

    # Test Case 2: Filter by 'meat'
    print("\nTest 2: Filter by tag=['meat']")
    result = r.recommend(tag_filters=['meat'])
    
    if result:
        tags = result.get('tags', [])
        print(f"Recommended: {result['name']} (Tags: {tags})")
        if 'meat' in tags:
            print("✅ PASS: Recommendation has 'meat' tag.")
        else:
            print(f"❌ FAIL: Recommendation {result['name']} does NOT have 'meat' tag.")
    else:
        print("❌ FAIL: No recommendation returned for meat.")

if __name__ == "__main__":
    verify_tag_filtering()
