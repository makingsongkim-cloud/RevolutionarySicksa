import recommender
from lunch_data import MENUS

def test_recommender():
    r = recommender.LunchRecommender()
    print("Testing basic recommendation...")
    rec = r.recommend(weather="맑음", mood="보통")
    print(f"Recommended: {rec['name']}")
    assert rec in MENUS
    print("Basic recommendation test passed.")

    # Test weight boosting (statistical test is hard, just checking no crash)
    print("Testing simple conditions...")
    rec_rain = r.recommend(weather="비", mood="스트레스")
    print(f"Rain/Stress Recommended: {rec_rain['name']}")
    
if __name__ == "__main__":
    test_recommender()
