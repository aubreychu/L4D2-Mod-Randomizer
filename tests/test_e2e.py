import os
import pytest
import asyncio
from PySide6.QtCore import Qt
from unittest.mock import patch, MagicMock

# Required for headless environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from main import L4D2RandomizerApp
from core.models import ModItem, ModEvaluation
from core.database import save_mods_to_pool, Base, engine

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    dummy_mod1 = ModItem(
        id="111",
        title="Cool AK47",
        tags=["weapons"],
        theme_tag="Any Theme",
        eval=ModEvaluation(model_slots=["AK-47"], audio_slots=["AK-47"], raw_paths=["models/v_models/v_rif_ak47.mdl"])
    )
    dummy_mod2 = ModItem(
        id="222",
        title="Cool M16",
        tags=["weapons"],
        theme_tag="Any Theme",
        eval=ModEvaluation(model_slots=["Assault Rifle (M16)"], audio_slots=["Assault Rifle (M16)"], raw_paths=["models/v_models/v_rif_m16a2.mdl"])
    )
    save_mods_to_pool([dummy_mod1, dummy_mod2])
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def app(qtbot):
    main_app = L4D2RandomizerApp()
    qtbot.addWidget(main_app)
    return main_app

def test_full_user_journey(app, qtbot, mocker):
    mocker.patch('core.director.USER_CONFIG', {"QOL_MODS": []})

    # Mock external APIs for scraper
    mock_fetch_page = mocker.AsyncMock(return_value=[
        {"publishedfileid": "333", "title": "Scraped Mod", "tags": [{"tag": "weapons"}]}
    ])
    mocker.patch('core.network.fetch_page', side_effect=mock_fetch_page)

    mock_fetch_details = mocker.AsyncMock(return_value=[
        {"publishedfileid": "333", "file_size": 1000, "subscriptions": 500, "file_url": "http", "preview_url": "http"}
    ])
    mocker.patch('core.network.fetch_details_chunk', side_effect=mock_fetch_details)

    mock_probe = mocker.AsyncMock()
    mocker.patch('core.scraper.probe_and_map_mod', side_effect=mock_probe)

    # 1. Launch App
    assert app is not None

    # 2. Simulate Passive Scraper Tab
    app.tabs.setCurrentIndex(2)
    assert app.tabs.currentIndex() == 2

    # Tick "Weapons" tag to ensure targets exist
    app.tag_vars["Weapons"].setChecked(True)

    qtbot.mouseClick(app.btn_start_scrape, Qt.LeftButton)
    assert not app.btn_start_scrape.isEnabled()
    assert app.btn_stop_scrape.isEnabled()

    # Wait a bit for the thread to start and run one iteration
    qtbot.wait(100)

    qtbot.mouseClick(app.btn_stop_scrape, Qt.LeftButton)
    assert app.btn_start_scrape.isEnabled()
    assert not app.btn_stop_scrape.isEnabled()

    # 3. Simulate "Pool Source" slider
    app.tabs.setCurrentIndex(0)
    app.ratio_slider.setValue(100) # Only local cache
    assert app.blend_mode == 1.0

    # 4. Generate Loadout
    with qtbot.waitSignal(app.signals.generation_complete, timeout=5000):
        qtbot.mouseClick(app.generate_btn, Qt.LeftButton)

    assert len(app.current_selected_ids) > 0
    assert "111" in app.current_selected_ids or "222" in app.current_selected_ids

    # 5. Deploy to Steam
    # Important: get_collection_items must return a list
    mocker.patch('core.director.get_collection_items', return_value=["999"])

    mock_modify = mocker.AsyncMock(return_value=True)
    mocker.patch('core.director.async_modify_collection', side_effect=mock_modify)

    with qtbot.waitSignal(app.signals.deploy_complete, timeout=5000):
        qtbot.mouseClick(app.play_btn, Qt.LeftButton)

    # Verify we removed old items and added new ones
    calls = mock_modify.call_args_list
    assert len(calls) > 0
    actions = [c.args[3] for c in calls]
    mod_ids = [c.args[2] for c in calls]

    assert "removechild" in actions
    assert "999" in mod_ids

    assert "addchild" in actions
    for sid in app.current_selected_ids:
        assert sid in mod_ids
