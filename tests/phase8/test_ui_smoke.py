def test_streamlit_app_importable():
    import importlib

    mod = importlib.import_module("ui.app")
    assert hasattr(mod, "main")
    assert callable(mod.main)
