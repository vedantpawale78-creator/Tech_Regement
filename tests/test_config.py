import pytest
import os
import yaml
from config_loader import load_config

def test_load_config():
    test_yaml = """
model:
  path: test.pt
"""
    with open('test_config.yaml', 'w') as f:
        f.write(test_yaml)
        
    config = load_config('test_config.yaml')
    assert config['model']['path'] == 'test.pt'
    
    os.remove('test_config.yaml')
    
def test_missing_config():
    with pytest.raises(FileNotFoundError):
        load_config('non_existent.yaml')
