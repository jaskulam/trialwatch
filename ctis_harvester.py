import os, asyncio, time, pendulum, boto3, hashlib
from pathlib import Path
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.async_api import async_playwright

load_dotenv()

DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "90"))
S3_BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("AWS_REGION", "eu-west-1")

SEARCH_URL = (
    "https://euclinicaltrials.eu/search-for-clinical-trials"
)

# ---------- helpers ----------

def today_path() -> Path:
    ts = pendulum.yesterday().format("YYYY-MM-DD")
    tmp = Path("/tmp") / f"ctis_{ts}.csv"
    tmp.parent.mkdir(exist_ok=True, parents=True)
    return tmp

def upload_to_s3(local_path: Path) -> str:
    s3 = boto3.client("s3", region_name=REGION)
    key = f"raw/{local_path.name}"
    s3.upload_file(str(local_path), S3_BUCKET, key)
    # 7-dniowy presigned URL (na potrzeby debugowania)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )

# ---------- core ----------

@retry(wait=wait_exponential(multiplier=2, min=4, max=30),
       stop=stop_after_attempt(3))
async def run():
    out_path = today_path()
    if out_path.exists():
        print("✔ CSV już pobrany.")
        return upload_to_s3(out_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()

        # Interceptujemy wszystkie żądania, by wychwycić link CSV
        download_url = None
        def handle_request(request):
            nonlocal download_url
            url = request.url
            if "download" in url and url.endswith(".csv"):
                download_url = url
        page.on("request", handle_request)

        await page.goto(SEARCH_URL, timeout=60000)
        # 1) otwórz filtr advanced
        await page.locator("button:has-text('Advanced filters')").click()
        # 2) ustaw "Last updated" na wczoraj
        await page.locator("label:has-text('Last updated')").click()
        yesterday = pendulum.yesterday().format("DD/MM/YYYY")
        input_box = page.locator("input[placeholder='DD/MM/YYYY']").first
        await input_box.fill(yesterday)
        await input_box.press("Enter")
        # 3) kliknij Download CSV
        with page.expect_download(timeout=DOWNLOAD_TIMEOUT * 1000) as dl_info:
            await page.locator("button:has-text('Download CSV')").click()
        download = await dl_info.value
        csv_path = await download.path()
        Path(csv_path).rename(out_path)
        await browser.close()

    print(f"✔ Zapisano {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")
    return upload_to_s3(out_path)

# ---------- entry ----------

if __name__ == "__main__":
    url = asyncio.run(run())
    print("Presigned URL (debug):", url)
