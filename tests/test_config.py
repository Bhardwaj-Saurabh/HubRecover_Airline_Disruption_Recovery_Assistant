import os
from hubrecover.config import load_local_environment


def test_local_env_loads_only_model_settings_and_preserves_explicit_environment(tmp_path,monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False)
    monkeypatch.setenv('HUBRECOVER_GEMINI_MODEL','explicit-model')
    monkeypatch.delenv('HUBRECOVER_UNRELATED_SETTING',raising=False)
    path=tmp_path/'.env'
    path.write_text('GOOGLE_API_KEY="synthetic-test-key"\nHUBRECOVER_GEMINI_MODEL=file-model\nHUBRECOVER_UNRELATED_SETTING=ignored\n')
    load_local_environment(path)
    assert os.environ['GOOGLE_API_KEY']=='synthetic-test-key'
    assert os.environ['HUBRECOVER_GEMINI_MODEL']=='explicit-model'
    assert 'HUBRECOVER_UNRELATED_SETTING' not in os.environ


def test_missing_file_and_literal_dollar_values(tmp_path,monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False)
    monkeypatch.delenv('HUBRECOVER_GEMINI_MODEL',raising=False)
    load_local_environment(tmp_path/'absent')
    assert 'GOOGLE_API_KEY' not in os.environ
    path=tmp_path/'.env';path.write_text('GOOGLE_API_KEY=${DO_NOT_EXPAND}\n')
    load_local_environment(path)
    assert os.environ['GOOGLE_API_KEY']=='${DO_NOT_EXPAND}'
