from pathlib import Path
import re


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
STATIC_DIR = PACKAGE_ROOT / "static"


def test_user_menu_exposes_explicit_redeem_entry():
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")

    assert "兑换次数" in user_menu
    assert user_menu.count('to="/credits"') == 1


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
    assert "账号次数与自带 API 双模式" not in welcome_page
    assert "论文原创性工作台" not in welcome_page
    assert "功能介绍" not in welcome_page
    assert "使用场景" not in welcome_page
    assert "安全保障" not in welcome_page
    assert "Word 排版" not in welcome_page


def test_user_menu_hides_word_formatter_entry_until_feature_is_ready():
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")

    assert "Word 排版" not in user_menu
    assert 'to="/word-formatter"' not in user_menu


def test_admin_dashboard_hides_legacy_card_key_management():
    admin_dashboard = (FRONTEND_SRC / "pages" / "AdminDashboard.jsx").read_text(encoding="utf-8")

    assert "次数兑换码" in admin_dashboard
    assert "用户次数余额" in admin_dashboard
    assert "邀请码、兑换码和用户余额统一在这里管理。" not in admin_dashboard
    assert "前往管理" not in admin_dashboard
    assert "生成卡密" not in admin_dashboard
    assert "批量生成" not in admin_dashboard
    assert "使用次数" not in admin_dashboard
    assert "/api/admin/card-keys" not in admin_dashboard
    assert "/api/admin/batch-generate-keys" not in admin_dashboard
    assert "/api/admin/users/${userId}/usage" not in admin_dashboard


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
        assert "平台次数" in source
        assert "自带 API" in source
    assert "已使用:" not in page
    assert "使用量:" not in spec_page
    assert "使用量:" not in preprocess_page


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
    assert "账号次数与自带 API 双模式" not in static_bundle
    assert "论文原创性工作台" not in static_bundle
    assert "功能介绍" not in static_bundle
    assert "使用场景" not in static_bundle
    assert "安全保障" not in static_bundle
