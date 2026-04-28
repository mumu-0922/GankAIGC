from pathlib import Path
import re


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PACKAGE_ROOT / "frontend"
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
STATIC_DIR = PACKAGE_ROOT / "static"


def test_user_menu_exposes_explicit_redeem_entry():
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")

    assert "兑换额度" in user_menu
    assert "千字额度" in user_menu
    assert user_menu.count('to="/credits"') == 1


def test_credit_transactions_render_backend_utc_as_china_time():
    date_utils = (FRONTEND_SRC / "utils" / "dateTime.js").read_text(encoding="utf-8")
    credits_page = (FRONTEND_SRC / "pages" / "CreditsPage.jsx").read_text(encoding="utf-8")

    assert "Asia/Shanghai" in date_utils
    assert "endsWith('Z')" in date_utils
    assert "formatChinaDateTime" in credits_page
    assert "formatChinaDateTime(transaction.created_at)" in credits_page
    assert "new Date(transaction.created_at).toLocaleString()" not in credits_page


def test_served_static_bundle_includes_china_time_formatter():
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    bundle_match = re.search(r'src="/assets/(index-[^"]+\.js)"', static_index)
    assert bundle_match

    static_bundle = (STATIC_DIR / "assets" / bundle_match.group(1)).read_text(encoding="utf-8")

    assert "Asia/Shanghai" in static_bundle
    assert "hour12" in static_bundle


def test_frontend_uses_brand_logo_as_favicon():
    frontend_index = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    brand_logo = (FRONTEND_SRC / "components" / "BrandLogo.jsx").read_text(encoding="utf-8")

    for index_html in (frontend_index, static_index):
        assert 'rel="icon"' in index_html
        assert 'type="image/svg+xml"' in index_html
        assert 'href="/gankaigc-logo.svg"' in index_html
        assert "/shiliang.svg" not in index_html
        assert "/vite.svg" not in index_html

    for logo_path in (FRONTEND_ROOT / "public" / "gankaigc-logo.svg", STATIC_DIR / "gankaigc-logo.svg"):
        logo_svg = logo_path.read_text(encoding="utf-8")

        assert 'viewBox="442 369 1180 1180"' in logo_svg
        assert 'preserveAspectRatio="xMidYMid meet"' in logo_svg
        assert 'viewBox="0 0 2048 2048"' not in logo_svg
        assert 'preserveAspectRatio="none"' not in logo_svg

    assert not (FRONTEND_ROOT / "public" / "shiliang.svg").exists()
    assert not (STATIC_DIR / "shiliang.svg").exists()
    assert not (FRONTEND_ROOT / "public" / "gankaigc-logo.png").exists()
    assert not (STATIC_DIR / "gankaigc-logo.png").exists()
    assert 'src="/gankaigc-logo.svg"' in brand_logo
    assert "/shiliang.svg" not in brand_logo
    assert "/gankaigc-logo.png" not in brand_logo


def test_welcome_page_focuses_on_ai_reduction_not_word_formatting():
    welcome_page = (FRONTEND_SRC / "pages" / "WelcomePage.jsx").read_text(encoding="utf-8")

    assert "让论文原创更简单" in welcome_page
    assert "开始使用" in welcome_page
    assert "登录 / 注册" in welcome_page
    assert "优化前" in welcome_page
    assert "优化后" in welcome_page
    assert "AI 率检测结果" in welcome_page
    assert 'data-home-scenarios="workflow"' in welcome_page
    assert "论文处理链路" in welcome_page
    assert "阶段 01" in welcome_page
    assert "从初稿到投稿前的三步优化" in welcome_page
    assert "阶段 04" not in welcome_page
    assert "有自有模型额度时，可切换为自带 API 模式" not in welcome_page
    assert "账号次数与自带 API 双模式" not in welcome_page
    assert "论文原创性工作台" not in welcome_page
    assert "功能介绍" not in welcome_page
    assert "使用场景" not in welcome_page
    assert "安全保障" not in welcome_page
    assert "Word 排版" not in welcome_page


def test_welcome_page_links_to_github_project_and_requests_star():
    welcome_page = (FRONTEND_SRC / "pages" / "WelcomePage.jsx").read_text(encoding="utf-8")

    assert "https://github.com/mumu-0922/GankAIGC" in welcome_page
    assert "GitHub 项目" in welcome_page
    assert "求 Star" in welcome_page
    assert 'data-home-github-star="footer"' in welcome_page
    assert welcome_page.count("GitHub 项目") == 1
    assert welcome_page.index('data-home-scenarios="workflow"') < welcome_page.index("GitHub 项目")
    assert 'target="_blank"' in welcome_page
    assert 'rel="noopener noreferrer"' in welcome_page


def test_workspace_queue_status_uses_processing_task_label():
    workspace = (FRONTEND_SRC / "pages" / "WorkspacePage.jsx").read_text(encoding="utf-8")

    assert "ListChecks" in workspace
    assert "处理中 {queueStatus.current_users}/{queueStatus.max_users}" in workspace
    assert "Users className" not in workspace


def test_user_menu_hides_word_formatter_entry_until_feature_is_ready():
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")

    assert "Word 排版" not in user_menu
    assert 'to="/word-formatter"' not in user_menu


def test_admin_dashboard_hides_legacy_card_key_management():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "额度兑换码" in admin_dashboard
    assert "用户额度余额" in admin_dashboard
    assert "按千字额度" in admin_dashboard
    assert "无限额度" in admin_dashboard
    assert "邀请码、兑换码和用户余额统一在这里管理。" not in admin_dashboard
    assert "前往管理" not in admin_dashboard
    assert "生成卡密" not in admin_dashboard
    assert "批量生成" not in admin_dashboard
    assert "使用次数" not in admin_dashboard
    assert "账号次数" not in admin_dashboard
    assert "无限调用" not in admin_dashboard
    assert "/api/admin/card-keys" not in admin_dashboard
    assert "/api/admin/batch-generate-keys" not in admin_dashboard
    assert "/api/admin/users/${userId}/usage" not in admin_dashboard


def test_admin_dashboard_hides_word_formatter_statistics_until_feature_is_ready():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "statistics.word_formatter" not in admin_dashboard
    assert "排版任务" not in admin_dashboard
    assert "Word 排版任务" not in admin_dashboard


def test_database_manager_honors_backend_read_only_flag():
    database_manager = (FRONTEND_SRC / "components" / "DatabaseManager.jsx").read_text(encoding="utf-8")

    assert "canWrite" in database_manager
    assert "response.data.can_write" in database_manager
    assert "只读模式" in database_manager
    assert "canWrite && (" in database_manager
    assert "{canWrite && editingRecord && (" in database_manager


def test_admin_dashboard_does_not_duplicate_session_monitor_status_metrics():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "data-admin-session-status" not in admin_dashboard
    assert "完成会话" not in admin_dashboard
    assert "排队等待" not in admin_dashboard
    assert "失败会话" not in admin_dashboard
    assert "完成进度" not in admin_dashboard
    assert "data-admin-processing-summary" in admin_dashboard
    assert "平均输入规模" in admin_dashboard


def test_admin_dashboard_shows_all_processing_mode_counts():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "data-admin-processing-modes" in admin_dashboard
    assert "论文润色" in admin_dashboard
    assert "论文增强" in admin_dashboard
    assert "润色 + 增强" in admin_dashboard
    assert "感情文章润色" in admin_dashboard
    assert "processingStats.paper_polish_count" in admin_dashboard
    assert "processingStats.paper_enhance_count" in admin_dashboard
    assert "processingStats.paper_polish_enhance_count" in admin_dashboard
    assert "processingStats.emotion_polish_count" in admin_dashboard


def test_admin_dashboard_uses_left_sidebar_navigation():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert 'data-admin-nav="sidebar"' in admin_dashboard
    assert 'data-admin-nav="top-tabs"' not in admin_dashboard
    assert "lg:grid-cols-[240px_minmax(0,1fr)]" in admin_dashboard
    assert "lg:min-h-[calc(100vh-8rem)]" in admin_dashboard


def test_admin_dashboard_preserves_selected_tab_in_url():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "useSearchParams" in admin_dashboard
    assert "searchParams.get('tab')" in admin_dashboard
    assert "setSearchParams" in admin_dashboard
    assert "handleAdminTabChange" in admin_dashboard
    assert "onClick={() => handleAdminTabChange(id)}" in admin_dashboard


def test_word_formatter_uses_platform_credits_or_user_api_not_legacy_card_key():
    routes = (PACKAGE_ROOT / "backend" / "app" / "word_formatter" / "routes.py").read_text(encoding="utf-8")
    api = (FRONTEND_SRC / "api" / "index.js").read_text(encoding="utf-8")
    page = (FRONTEND_SRC / "pages" / "WordFormatterPage.jsx").read_text(encoding="utf-8")
    spec_page = (FRONTEND_SRC / "pages" / "SpecGeneratorPage.jsx").read_text(encoding="utf-8")
    preprocess_page = (FRONTEND_SRC / "pages" / "ArticlePreprocessorPage.jsx").read_text(encoding="utf-8")

    assert "CreditService" in routes
    assert "ProviderConfigService" in routes
    assert "billing_mode" in routes
    assert "charge_word_formatter_platform_credit" in routes
    assert "get_word_formatter_ai_service" in routes
    assert "该卡密已达到使用次数限制" not in routes

    assert "billing_mode: options.billingMode" in api
    assert "billing_mode: billingMode" in page
    assert "generateSpec(requirements, { billingMode })" in spec_page
    assert "preprocessFile(file, {" in preprocess_page
    assert "billingMode," in preprocess_page
    for source in (page, spec_page, preprocess_page):
        assert "平台额度" in source
        assert "自带 API" in source
    assert "已使用:" not in page
    assert "使用量:" not in spec_page
    assert "使用量:" not in preprocess_page


def test_workspace_and_credits_explain_character_based_credit_billing():
    workspace = (FRONTEND_SRC / "pages" / "WorkspacePage.jsx").read_text(encoding="utf-8")
    credits_page = (FRONTEND_SRC / "pages" / "CreditsPage.jsx").read_text(encoding="utf-8")
    profile_page = (FRONTEND_SRC / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8")
    welcome_page = (FRONTEND_SRC / "pages" / "WelcomePage.jsx").read_text(encoding="utf-8")
    readme = (PACKAGE_ROOT.parent / "README.md").read_text(encoding="utf-8")

    assert "1000 非空白字符 = 1 额度" in workspace
    assert "预计消耗 {estimatedCredits} 千字额度" in workspace
    assert "平台千字额度不足" in workspace
    assert "平台千字额度" in credits_page
    assert "1000 个非空白字符" in credits_page
    assert "剩余千字额度" in profile_page
    assert "按千字额度使用" in welcome_page
    assert "兑换码充值额度" in readme
    assert "平台模式按字符折算额度" in readme
    assert "兑换码充值次数" not in readme
    assert "平台次数模式" not in readme


def test_frontend_exposes_profile_page_and_nickname_update():
    app = (FRONTEND_SRC / "App.jsx").read_text(encoding="utf-8")
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")
    api = (FRONTEND_SRC / "api" / "index.js").read_text(encoding="utf-8")
    profile_page = (FRONTEND_SRC / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8")

    assert 'path="/profile"' in app
    assert 'to="/profile"' in user_menu
    assert "个人信息" in user_menu
    assert "nickname" in profile_page
    assert "保存昵称" in profile_page
    assert "updateProfile" in api


def test_frontend_exposes_user_invite_generation_on_profile_page():
    api = (FRONTEND_SRC / "api" / "index.js").read_text(encoding="utf-8")
    profile_page = (FRONTEND_SRC / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8")

    assert "getMyInvite" in api
    assert "createMyInvite" in api
    assert "/user/invites/my" in api
    assert "/user/invites" in api
    assert "我的邀请码" in profile_page
    assert "生成邀请码" in profile_page
    assert "复制邀请码" in profile_page
    assert "每个账号仅可生成 1 个邀请码" in profile_page
    assert "使用后可再次生成" not in profile_page


def test_frontend_removes_legacy_card_key_and_dead_prompt_manager():
    app = (FRONTEND_SRC / "App.jsx").read_text(encoding="utf-8")
    api = (FRONTEND_SRC / "api" / "index.js").read_text(encoding="utf-8")
    session_monitor = (FRONTEND_SRC / "components" / "SessionMonitor.jsx").read_text(encoding="utf-8")

    assert 'path="/access/:cardKey"' not in app
    assert not (FRONTEND_SRC / "components" / "PromptManager.jsx").exists()
    assert "export const promptsAPI" not in api
    assert "export const healthAPI" not in api
    assert "export const adminAPI" not in api
    assert "admin_password" not in api
    assert "adminAPI" not in session_monitor
    assert "prompt(" not in session_monitor
    assert "getSessionUserLabel" in session_monitor
    assert "session.user_display_name" in session_monitor
    assert "用户会话历史: {selectedUser.label}" in session_monitor
    assert "用户会话历史: {selectedUser.card_key}" not in session_monitor


def test_package_main_no_longer_registers_legacy_access_page():
    package_main = (PACKAGE_ROOT / "main.py").read_text(encoding="utf-8")

    assert '@app.get("/access/{card_key}")' not in package_main
    assert "async def serve_access" not in package_main


def test_session_export_modal_only_offers_word_and_markdown():
    session_detail = (FRONTEND_SRC / "pages" / "SessionDetailPage.jsx").read_text(encoding="utf-8")
    api = (FRONTEND_SRC / "api" / "index.js").read_text(encoding="utf-8")

    assert "useState('docx')" in session_detail
    assert '<option value="docx">Word文档 (.docx)</option>' in session_detail
    assert '<option value="md">Markdown文件 (.md)</option>' in session_detail
    assert 'value="txt"' not in session_detail
    assert 'value="pdf"' not in session_detail
    assert "即将支持" not in session_detail
    assert "content_base64" in session_detail
    assert "mime_type" in session_detail
    assert "responseType" not in api


def test_api_config_guide_lists_current_model_recommendations():
    api_guide = (FRONTEND_SRC / "components" / "ApiConfigGuide.jsx").read_text(encoding="utf-8")

    for model_name in [
        "gpt-5.5",
        "gpt-5.4",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ]:
        assert model_name in api_guide

    for legacy_model_name in [
        "gemini-2.5-pro",
        "gemini-3-pro-preview",
        "claude-sonnet-4-20250514",
        "deepseek-chat",
        "gpt-5.2",
    ]:
        assert legacy_model_name not in api_guide


def test_config_manager_uses_current_model_placeholders():
    config_manager = (FRONTEND_SRC / "components" / "ConfigManager.jsx").read_text(encoding="utf-8")

    assert config_manager.count('placeholder="gpt-5.5"') == 4
    assert 'placeholder="gemini-2.5-pro"' not in config_manager


def test_config_manager_hides_word_formatter_file_size_setting_until_feature_is_ready():
    config_manager = (FRONTEND_SRC / "components" / "ConfigManager.jsx").read_text(encoding="utf-8")

    assert "Word 排版文件大小限制" not in config_manager
    assert "MAX_UPLOAD_FILE_SIZE_MB" not in config_manager
    assert "max_upload_file_size_mb" not in config_manager
    assert "0 表示无限制" not in config_manager


def test_config_manager_exposes_registration_enabled_switch():
    config_manager = (FRONTEND_SRC / "components" / "ConfigManager.jsx").read_text(encoding="utf-8")

    assert "REGISTRATION_ENABLED" in config_manager
    assert "账号注册控制" in config_manager
    assert "允许新用户通过邀请码注册" in config_manager
    assert "response.data.system.registration_enabled" in config_manager


def test_api_config_guide_keeps_previous_sections_open_when_expanding_next():
    api_guide = (FRONTEND_SRC / "components" / "ApiConfigGuide.jsx").read_text(encoding="utf-8")

    assert "activeSections.includes(id)" in api_guide
    assert "setActiveSections((previousSections)" in api_guide
    assert "previousSections.filter((sectionId) => sectionId !== id)" in api_guide
    assert "return [...previousSections, id]" in api_guide
    assert "activeSection === id" not in api_guide
    assert "setActiveSection(isActive ? null : id)" not in api_guide
    assert 'data-api-guide-multi-expand="true"' in api_guide
    assert api_guide.count('type="button"') >= 3


def test_api_config_guide_preserves_scroll_position_when_toggling_sections():
    api_guide = (FRONTEND_SRC / "components" / "ApiConfigGuide.jsx").read_text(encoding="utf-8")

    assert "preserveScrollPosition" in api_guide
    assert "window.requestAnimationFrame" in api_guide
    assert "window.scrollTo(scrollX, scrollY)" in api_guide
    assert "preserveScrollPosition(() => {" in api_guide


def test_api_config_guide_links_to_current_project_issues():
    api_guide = (FRONTEND_SRC / "components" / "ApiConfigGuide.jsx").read_text(encoding="utf-8")

    assert "https://github.com/mumu-0922/GankAIGC/issues" in api_guide
    assert "https://github.com/chi111i/GankAIGC/issues" not in api_guide


def test_frontend_examples_avoid_secret_scanner_key_prefixes():
    api_guide = (FRONTEND_SRC / "components" / "ApiConfigGuide.jsx").read_text(encoding="utf-8")
    config_manager = (FRONTEND_SRC / "components" / "ConfigManager.jsx").read_text(encoding="utf-8")
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    bundle_match = re.search(r'src="/assets/(index-[^"]+\.js)"', static_index)
    assert bundle_match

    static_bundle = (STATIC_DIR / "assets" / bundle_match.group(1)).read_text(encoding="utf-8")
    google_key_prefix = "AI" + "za"

    for source in (api_guide, config_manager, static_bundle):
        assert google_key_prefix not in source

    assert "Google API Key" in api_guide
    assert "Google API Key" in config_manager


def test_served_static_bundle_includes_api_guide_interaction_fix():
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    bundle_match = re.search(r'src="/assets/(index-[^"]+\.js)"', static_index)
    assert bundle_match

    static_bundle = (STATIC_DIR / "assets" / bundle_match.group(1)).read_text(encoding="utf-8")

    assert "data-api-guide-multi-expand" in static_bundle
    assert "gemini-3.1-pro-preview" in static_bundle
    assert "gpt-5.5" in static_bundle
    assert "requestAnimationFrame" in static_bundle
    assert "scrollTo" in static_bundle
    assert "https://github.com/mumu-0922/GankAIGC/issues" in static_bundle
    assert "https://github.com/chi111i/GankAIGC/issues" not in static_bundle


def test_served_static_bundle_includes_admin_tab_url_persistence():
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    bundle_match = re.search(r'src="/assets/(index-[^"]+\.js)"', static_index)
    assert bundle_match

    static_bundle = (STATIC_DIR / "assets" / bundle_match.group(1)).read_text(encoding="utf-8")

    assert "URLSearchParams" in static_bundle
    assert '"tab"' in static_bundle
    assert '"dashboard","sessions","accounts","database","config"' in static_bundle
    assert "Word 排版文件大小限制" not in static_bundle
    assert "MAX_UPLOAD_FILE_SIZE_MB" not in static_bundle
    assert "max_upload_file_size_mb" not in static_bundle
    assert "排版任务" not in static_bundle


def test_served_static_bundle_includes_ai_reduction_homepage():
    static_index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    bundle_match = re.search(r'src="/assets/(index-[^"]+\.js)"', static_index)
    assert bundle_match

    static_bundle = (STATIC_DIR / "assets" / bundle_match.group(1)).read_text(encoding="utf-8")

    assert "让论文原创更简单" in static_bundle
    assert "登录 / 注册" in static_bundle
    assert "优化前" in static_bundle
    assert "优化后" in static_bundle
    assert "AI 率检测结果" in static_bundle
    assert "data-home-scenarios" in static_bundle
    assert "论文处理链路" in static_bundle
    assert "阶段 01" in static_bundle
    assert "从初稿到投稿前的三步优化" in static_bundle
    assert "阶段 04" not in static_bundle
    assert "有自有模型额度时，可切换为自带 API 模式" not in static_bundle
    assert "账号次数与自带 API 双模式" not in static_bundle
    assert "论文原创性工作台" not in static_bundle
    assert "功能介绍" not in static_bundle
    assert "使用场景" not in static_bundle
    assert "安全保障" not in static_bundle
    assert "https://github.com/mumu-0922/GankAIGC" in static_bundle
    assert "GitHub 项目" in static_bundle
    assert "求 Star" in static_bundle
    assert "data-home-github-star" in static_bundle
