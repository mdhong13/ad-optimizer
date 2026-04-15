"""
생성된 마케팅 카피를 Google Sheet Marketing_Text 시트에 정리
서비스 계정 사용: quantumcat-f7570-84c35c53a6c2.json
"""
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = r"D:\0_닷셀\One Message\quantumcat-f7570-84c35c53a6c2.json"
SPREADSHEET_ID = "1bMnB5dj-C4lDAFtunK5O4EZeKWPnw5FNCpqAgl6rHCY"
SHEET_NAME = "Marketing_Text"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

GENERATED_DIR = "D:/0_Dotcell/ad-optimizer/docs/generated"


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def load_json(filename):
    path = os.path.join(GENERATED_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_rows():
    """모든 마케팅 카피를 시트 행으로 변환"""
    rows = []

    # === 헤더 ===
    rows.append(["Category", "Sub-Category", "Type", "Language", "Title/Headline", "Body/Description", "CTA/Keywords", "Notes"])
    rows.append([])  # 빈 행

    # === 1. 메인 페이지 카피 ===
    main = load_json("main_page.json")

    rows.append(["=== 메인 페이지 (Main Page) ===", "", "", "", "", "", "", ""])
    rows.append([])

    # Main Titles
    rows.append(["Main Titles", "", "", "", "", "", "", ""])
    for i, item in enumerate(main.get("main_titles", []), 1):
        rows.append(["Main Title", f"#{i}", "Title", "KR", item.get("title_kr", ""), item.get("subtitle_kr", ""), "", ""])
        rows.append(["Main Title", f"#{i}", "Title", "EN", item.get("title_en", ""), item.get("subtitle_en", ""), "", ""])
    rows.append([])

    # Hero Copy
    rows.append(["Hero Copy", "", "", "", "", "", "", ""])
    for item in main.get("hero_copy", []):
        angle = item.get("angle", "")
        rows.append(["Hero Copy", angle, "Headline+Body", "KR",
                      item.get("headline_kr", ""), item.get("body_kr", ""),
                      item.get("cta_kr", ""), f"Angle: {angle}"])
        rows.append(["Hero Copy", angle, "Headline+Body", "EN",
                      item.get("headline_en", ""), item.get("body_en", ""),
                      item.get("cta_en", ""), f"Angle: {angle}"])
    rows.append([])

    # Taglines
    rows.append(["Taglines", "", "", "", "", "", "", ""])
    for i, item in enumerate(main.get("taglines", []), 1):
        rows.append(["Tagline", f"#{i}", "Tagline", "KR", item.get("kr", ""), "", "", ""])
        rows.append(["Tagline", f"#{i}", "Tagline", "EN", item.get("en", ""), "", "", ""])
    rows.append([])

    # === 2. 광고 소재 ===
    ads = load_json("ad_creatives.json")

    rows.append(["=== 광고 소재 (Ad Creatives) ===", "", "", "", "", "", "", ""])
    rows.append([])

    # Google Ads - Search
    rows.append(["Google Ads - Search", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("google_ads", {}).get("search", []), 1):
        # KR 버전
        h1 = item.get("headline_1_kr", item.get("headline_1", ""))
        h2 = item.get("headline_2_kr", item.get("headline_2", ""))
        h3 = item.get("headline_3_kr", item.get("headline_3", ""))
        d1 = item.get("description_1_kr", item.get("description_1", ""))
        d2 = item.get("description_2_kr", item.get("description_2", ""))
        kw = ", ".join(item.get("target_keywords_kr", item.get("target_keywords", [])))
        rows.append(["Google Search", f"Set #{i}", "Search Ad", "KR",
                      f"{h1} | {h2} | {h3}", f"{d1}\n{d2}", kw, ""])
        # EN 버전
        h1 = item.get("headline_1_en", "")
        h2 = item.get("headline_2_en", "")
        h3 = item.get("headline_3_en", "")
        d1 = item.get("description_1_en", "")
        d2 = item.get("description_2_en", "")
        kw = ", ".join(item.get("target_keywords_en", []))
        if h1:
            rows.append(["Google Search", f"Set #{i}", "Search Ad", "EN",
                          f"{h1} | {h2} | {h3}", f"{d1}\n{d2}", kw, ""])
    rows.append([])

    # Google Ads - Display
    rows.append(["Google Ads - Display", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("google_ads", {}).get("display", []), 1):
        h_kr = item.get("headline_kr", item.get("headline", ""))
        lh_kr = item.get("long_headline_kr", item.get("long_headline", ""))
        d_kr = item.get("description_kr", item.get("description", ""))
        img = item.get("image_suggestion_kr", item.get("image_suggestion", ""))
        rows.append(["Google Display", f"Set #{i}", "Display Ad", "KR",
                      h_kr, f"{lh_kr}\n{d_kr}", "", f"Image: {img}"])
        h_en = item.get("headline_en", "")
        lh_en = item.get("long_headline_en", "")
        d_en = item.get("description_en", "")
        img_en = item.get("image_suggestion_en", item.get("image_suggestion", ""))
        if h_en:
            rows.append(["Google Display", f"Set #{i}", "Display Ad", "EN",
                          h_en, f"{lh_en}\n{d_en}", "", f"Image: {img_en}"])
    rows.append([])

    # Meta - Facebook
    rows.append(["Meta Ads - Facebook", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("meta_ads", {}).get("facebook", []), 1):
        hl_kr = item.get("headline_kr", item.get("headline", ""))
        pt_kr = item.get("primary_text_kr", item.get("primary_text", ""))
        d_kr = item.get("description_kr", item.get("description", ""))
        cta = item.get("cta_kr", item.get("cta", ""))
        img = item.get("image_suggestion_kr", item.get("image_suggestion", ""))
        tgt = item.get("target_audience_kr", item.get("target_audience", ""))
        rows.append(["Facebook", f"Set #{i}", "Feed Ad", "KR",
                      hl_kr, pt_kr, cta, f"Target: {tgt} | Image: {img}"])
        hl_en = item.get("headline_en", "")
        pt_en = item.get("primary_text_en", "")
        cta_en = item.get("cta_en", "")
        if hl_en:
            rows.append(["Facebook", f"Set #{i}", "Feed Ad", "EN",
                          hl_en, pt_en, cta_en, f"Target: {item.get('target_audience_en','')}"])
    rows.append([])

    # Meta - Instagram
    rows.append(["Meta Ads - Instagram", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("meta_ads", {}).get("instagram", []), 1):
        cap_kr = item.get("caption_kr", item.get("caption", ""))
        img = item.get("image_suggestion_kr", item.get("image_suggestion", ""))
        story = item.get("story_text_kr", item.get("story_text", ""))
        rows.append(["Instagram", f"Set #{i}", "Post/Story", "KR",
                      story, cap_kr, "", f"Image: {img}"])
        cap_en = item.get("caption_en", "")
        story_en = item.get("story_text_en", "")
        if cap_en or story_en:
            rows.append(["Instagram", f"Set #{i}", "Post/Story", "EN",
                          story_en, cap_en, "", ""])
    rows.append([])

    # Twitter/X
    rows.append(["Twitter/X", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("twitter_x", []), 1):
        tweet_kr = item.get("tweet_text_kr", item.get("tweet_text", ""))
        thread_kr = item.get("thread_hook_kr", item.get("thread_hook", ""))
        img = item.get("image_suggestion_kr", item.get("image_suggestion", ""))
        rows.append(["Twitter/X", f"Set #{i}", "Tweet", "KR",
                      tweet_kr, thread_kr, "", f"Image: {img}"])
        tweet_en = item.get("tweet_text_en", "")
        thread_en = item.get("thread_hook_en", "")
        if tweet_en:
            rows.append(["Twitter/X", f"Set #{i}", "Tweet", "EN",
                          tweet_en, thread_en, "", ""])
    rows.append([])

    # Reddit
    rows.append(["Reddit", "", "", "", "", "", "", ""])
    for i, item in enumerate(ads.get("reddit", []), 1):
        title_kr = item.get("title_kr", item.get("title", ""))
        body_kr = item.get("body_kr", item.get("body", ""))
        sub = item.get("target_subreddit_kr", item.get("target_subreddit", ""))
        angle = item.get("angle_kr", item.get("angle", ""))
        rows.append(["Reddit", f"Set #{i}", "Post", "KR",
                      title_kr, body_kr, f"r/{sub}", f"Angle: {angle}"])
        title_en = item.get("title_en", "")
        body_en = item.get("body_en", "")
        if title_en:
            rows.append(["Reddit", f"Set #{i}", "Post", "EN",
                          title_en, body_en, f"r/{sub}", f"Angle: {angle}"])
    rows.append([])

    # === 3. 콘텐츠 마케팅 ===
    content = load_json("content_marketing.json")

    rows.append(["=== 콘텐츠 마케팅 (Content Marketing) ===", "", "", "", "", "", "", ""])
    rows.append([])

    # Blog Titles
    rows.append(["Blog Titles", "", "", "", "", "", "", ""])
    for i, item in enumerate(content.get("blog_titles", []), 1):
        cat = item.get("category", "")
        kw_kr = ", ".join(item.get("seo_keywords_kr", []))
        kw_en = ", ".join(item.get("seo_keywords_en", []))
        rows.append(["Blog", f"#{i}", cat, "KR",
                      item.get("title_kr", ""), item.get("outline_kr", ""), kw_kr, ""])
        rows.append(["Blog", f"#{i}", cat, "EN",
                      item.get("title_en", ""), item.get("outline_en", ""), kw_en, ""])
    rows.append([])

    # Email Subject Lines
    rows.append(["Email Subject Lines", "", "", "", "", "", "", ""])
    for i, item in enumerate(content.get("email_subject_lines", []), 1):
        rows.append(["Email", f"#{i}", "Subject", "KR",
                      item.get("subject_kr", ""), item.get("preview_kr", ""), "", ""])
        rows.append(["Email", f"#{i}", "Subject", "EN",
                      item.get("subject_en", ""), item.get("preview_en", ""), "", ""])
    rows.append([])

    # App Store Copy
    rows.append(["App Store Copy", "", "", "", "", "", "", ""])
    asc = content.get("app_store_copy", {})
    rows.append(["App Store", "Short Desc", "Description", "KR",
                  asc.get("short_description_kr", ""), "", "", ""])
    rows.append(["App Store", "Short Desc", "Description", "EN",
                  asc.get("short_description_en", ""), "", "", ""])
    rows.append(["App Store", "Long Desc", "Description", "KR",
                  "", asc.get("long_description_kr", ""), "", ""])
    rows.append(["App Store", "Long Desc", "Description", "EN",
                  "", asc.get("long_description_en", ""), "", ""])
    rows.append(["App Store", "What's New", "Update Note", "KR",
                  asc.get("whats_new_kr", ""), "", "", ""])
    rows.append(["App Store", "What's New", "Update Note", "EN",
                  asc.get("whats_new_en", ""), "", "", ""])
    kw_kr = ", ".join(asc.get("keywords_kr", []))
    kw_en = ", ".join(asc.get("keywords_en", []))
    rows.append(["App Store", "Keywords", "SEO", "KR",
                  "", "", kw_kr, ""])
    rows.append(["App Store", "Keywords", "SEO", "EN",
                  "", "", kw_en, ""])

    return rows


def ensure_sheet_exists(service, spreadsheet_id, sheet_name):
    """시트가 없으면 생성"""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]
    if sheet_name not in sheets:
        body = {
            "requests": [{
                "addSheet": {
                    "properties": {"title": sheet_name}
                }
            }]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()
        print(f"시트 '{sheet_name}' 생성됨")
    else:
        print(f"시트 '{sheet_name}' 이미 존재")


def write_to_sheet(rows):
    service = get_sheets_service()

    # 시트 존재 확인/생성
    ensure_sheet_exists(service, SPREADSHEET_ID, SHEET_NAME)

    # 기존 데이터 클리어
    range_name = f"{SHEET_NAME}!A1:H500"
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID, range=range_name
    ).execute()

    # 데이터 쓰기
    body = {"values": rows}
    result = service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        body=body,
    ).execute()

    updated = result.get("updatedRows", 0)
    print(f"Google Sheet 업데이트 완료: {updated}행 작성")
    return updated


def main():
    print("마케팅 카피 → Google Sheet 정리 시작...")
    rows = build_rows()
    print(f"총 {len(rows)}행 준비됨")
    count = write_to_sheet(rows)
    print(f"\n완료! https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")


if __name__ == "__main__":
    main()
