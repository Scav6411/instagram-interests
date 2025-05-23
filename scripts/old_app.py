from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from follow_scraper import scrape

# Initialize FastAPI app
app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Request model
class ScrapeRequest(BaseModel):
    usernames: list[str]
    followers_count: int | None = None  # None means scrape all
    following_count: int | None = None  # None means scrape all
    use_proxy: bool = False
    proxy_info: dict | None = None  # Example: {"host": "123.45.67.89", "port": "8080"}

@app.post("/scrape")
async def scrape_endpoint(request: ScrapeRequest):
    """
    API endpoint to trigger Instagram scraping.
    """
    try:
        logger.info(f"Received scrape request for usernames: {request.usernames}")
        scrape(
            usernames=request.usernames,
            followers_count=request.followers_count,
            following_count=request.following_count
        )
        return {"message": "Scraping completed successfully"}
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during scraping")
