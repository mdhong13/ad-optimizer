"""Google Ads API Basic Access 신청용 Design Document 생성"""
from fpdf import FPDF
from datetime import datetime


class DesignDoc(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, "Dotcell Co., Ltd. - Google Ads API Design Document", align="C", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 8, title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(10)
        self.multi_cell(190, 5.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(10)
        self.multi_cell(190, 5.5, "  - " + text)


pdf = DesignDoc()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# Title
pdf.set_font("Helvetica", "B", 16)
pdf.cell(0, 12, "OneMessage Ad Optimizer", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 6, "Google Ads API Integration Design Document", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, f"Date: {datetime.now().strftime('%Y-%m-%d')}  |  Version: 1.0", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, "Company: Dotcell Co., Ltd. (598-81-03648)", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(8)

# 1. Overview
pdf.section_title("1. Overview")
pdf.body_text(
    "OneMessage is a safety messaging mobile application developed by Dotcell Co., Ltd. "
    "The app allows users to compose messages that are automatically delivered to their "
    "designated contacts when the user becomes unresponsive for a configured period. "
    "This serves as a digital safety net for families, ensuring important information "
    "reaches loved ones when it matters most."
)
pdf.body_text(
    "The Ad Optimizer tool uses the Google Ads API to automate campaign management, "
    "performance monitoring, and budget optimization for OneMessage's advertising campaigns. "
    "The tool is used exclusively by Dotcell's internal engineering team."
)

# 2. API Usage
pdf.section_title("2. Google Ads API Usage")
pdf.body_text("The tool interacts with the following Google Ads API services:")
pdf.bullet("GoogleAdsService - Query campaign, ad group, and ad performance metrics")
pdf.bullet("CampaignService - Read campaign settings and status")
pdf.bullet("CampaignBudgetService - Monitor and adjust daily budgets")
pdf.bullet("AdGroupService - Read ad group configurations")
pdf.bullet("AdGroupAdService - Monitor ad-level performance")
pdf.bullet("KeywordPlanService - Research keyword opportunities")
pdf.ln(3)

# 3. Architecture
pdf.section_title("3. System Architecture")
pdf.body_text(
    "The Ad Optimizer follows a scheduled automation architecture:"
)
pdf.set_font("Courier", "", 9)
pdf.multi_cell(0, 5, (
    "  [Scheduler (APScheduler)]\n"
    "    |\n"
    "    +-- Every 1h: Collect performance data via Google Ads API\n"
    "    |              -> Store in local SQLite database\n"
    "    |\n"
    "    +-- Daily 09:00: Run optimization analysis\n"
    "    |                -> Generate budget adjustment recommendations\n"
    "    |                -> Execute approved changes via API\n"
    "    |\n"
    "    +-- Daily 20:00: Generate performance report\n"
    "                     -> Summarize daily metrics and changes"
))
pdf.ln(4)
pdf.set_font("Helvetica", "", 10)

# 4. Data Flow
pdf.section_title("4. Data Flow")
pdf.body_text("Step 1: Performance Data Collection")
pdf.body_text(
    "The system queries the Google Ads API (GoogleAdsService.SearchStream) to retrieve "
    "campaign-level metrics including impressions, clicks, conversions, cost, CTR, and CPC. "
    "Data is stored in a local SQLite database for historical analysis."
)
pdf.body_text("Step 2: Optimization Analysis")
pdf.body_text(
    "The system analyzes collected performance data to identify underperforming campaigns "
    "and budget reallocation opportunities. Recommendations are generated based on "
    "predefined rules (e.g., increase budget for campaigns with CPA below target, "
    "pause campaigns with zero conversions after threshold spend)."
)
pdf.body_text("Step 3: Action Execution")
pdf.body_text(
    "Approved optimization actions are executed via the Google Ads API. All changes "
    "are logged with timestamps, previous values, new values, and reasoning. "
    "Changes include budget adjustments and campaign status updates."
)

# 5. Authentication
pdf.section_title("5. Authentication & Security")
pdf.body_text(
    "The tool uses OAuth 2.0 authentication with a Desktop application client type. "
    "Credentials are stored in environment variables on the local development machine. "
    "The refresh token is used to obtain access tokens for API calls."
)
pdf.bullet("OAuth 2.0 Client Type: Desktop Application")
pdf.bullet("Token Storage: Local environment variables (.env file)")
pdf.bullet("Access Scope: https://www.googleapis.com/auth/adwords")
pdf.bullet("MCC Account: Used as login-customer-id for API access")
pdf.ln(3)

# 6. Rate Limiting
pdf.section_title("6. Rate Limiting & Quotas")
pdf.body_text(
    "The tool is designed to operate within Google Ads API rate limits. "
    "Expected API call volume:"
)
pdf.bullet("Performance data collection: ~24 SearchStream requests/day (hourly)")
pdf.bullet("Optimization actions: ~5-10 mutate requests/day")
pdf.bullet("Reporting queries: ~2-5 requests/day")
pdf.body_text(
    "Total estimated daily API calls: fewer than 50 requests. "
    "This is well within the Basic Access quota limits."
)

# 7. Error Handling
pdf.section_title("7. Error Handling")
pdf.bullet("API errors are caught and logged with full error details")
pdf.bullet("Failed mutations are retried up to 3 times with exponential backoff")
pdf.bullet("Authentication failures trigger a refresh token renewal flow")
pdf.bullet("All errors are reported in the daily summary report")
pdf.ln(3)

# 8. Compliance
pdf.section_title("8. Compliance & Data Handling")
pdf.bullet("No end-user personal data is accessed or stored via the API")
pdf.bullet("Only aggregate campaign performance metrics are collected")
pdf.bullet("The tool does not share any Google Ads data with third parties")
pdf.bullet("All data is stored locally and used solely for campaign optimization")
pdf.bullet("The tool complies with Google Ads API Terms of Service")

output_path = "D:/0_Dotcell/ad-optimizer/docs/google_ads_api_design_document.pdf"
pdf.output(output_path)
print(f"PDF saved: {output_path}")
