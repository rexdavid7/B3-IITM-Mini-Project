import importlib


def test_project_dotenv_loading_does_not_override_process_values(monkeypatch):
    import rfp_eval.config as config

    monkeypatch.setenv("GEMINI_MODEL", "process-model-setting")
    monkeypatch.setenv("GEMINI_API_KEY", "process-key-setting")
    importlib.reload(config)
    assert __import__("os").environ["GEMINI_MODEL"] == "process-model-setting"
    assert __import__("os").environ["GEMINI_API_KEY"] == "process-key-setting"
