from pathlib import Path


FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_user_menu_exposes_explicit_redeem_entry():
    user_menu = (FRONTEND_SRC / "components" / "UserMenu.jsx").read_text(encoding="utf-8")

    assert "兑换次数" in user_menu
    assert user_menu.count('to="/credits"') == 1


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
