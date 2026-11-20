from group_helper_bot.store import GroupStore
from group_helper_bot.ui import WELCOME, GUIDE, GROUP_GUIDE, home_keyboard


def test_home_menu_has_all_primary_sections():
    rows = home_keyboard()["inline_keyboard"]
    labels = [button["text"] for row in rows for button in row]
    assert any("دستیار" in label for label in labels)
    assert any("مدیریت گروه" in label for label in labels)
    assert any("راهنما" in label for label in labels)
    assert any("گزارش" in label for label in labels)
    assert "NOVA Help" in WELCOME
    assert "NOVA" in GUIDE
    assert "مدیران" in GROUP_GUIDE


def test_group_rules_are_persisted_and_updated(tmp_path):
    store = GroupStore(str(tmp_path / "groups.sqlite3"))
    assert store.get_rules("-100123") is None
    store.set_rules("-100123", "احترام به اعضا", "42")
    assert store.get_rules("-100123") == "احترام به اعضا"
    store.set_rules("-100123", "قوانین جدید", "43")
    assert store.get_rules("-100123") == "قوانین جدید"


def test_warning_counter_is_scoped_to_group_and_user(tmp_path):
    store = GroupStore(str(tmp_path / "groups.sqlite3"))
    assert store.add_warning("-1001", "7") == 1
    assert store.add_warning("-1001", "7") == 2
    assert store.add_warning("-1002", "7") == 1
    assert store.add_warning("-1001", "8") == 1


def test_support_reports_are_saved(tmp_path):
    store = GroupStore(str(tmp_path / "groups.sqlite3"))
    report_id = store.add_report("123", "test_user", "دکمه راهنما کار نمی‌کند")
    assert report_id == 1
