import pytest
from backend.api import Api

def test_fallback_naming_removes_invalid_chars(mocker):
    api = Api()
    mocker.patch('os.makedirs')
    mock_split_and_save = mocker.patch.object(api.pdf_processor, 'split_and_save', return_value='/tmp/mock.pdf')
    mocker.patch.object(api, 'send_status')

    preview_data = [
        {
            "original_file": "/tmp/orig.pdf",
            "start_page": 1,
            "end_page": 2,
            "short_name": 'Акт:*?"<>|',
            "date": "15/05/2026\\"
        }
    ]

    saved = api.save_documents(preview_data, "/tmp/out")
    
    assert len(saved) == 1
    mock_split_and_save.assert_called_once()
    called_args = mock_split_and_save.call_args[0]
    # new_name is the 4th argument (index 3)
    # The invalid chars \/*?:"<>| should be stripped
    assert called_args[3] == "Акт 15052026"

def test_fallback_naming_removes_error_keyword(mocker):
    api = Api()
    mocker.patch('os.makedirs')
    mock_split_and_save = mocker.patch.object(api.pdf_processor, 'split_and_save', return_value='/tmp/mock.pdf')
    mocker.patch.object(api, 'send_status')

    preview_data = [
        {
            "original_file": "/tmp/orig.pdf",
            "start_page": 1,
            "end_page": 2,
            "short_name": "ОшибкаАкт",
            "date": "2026"
        }
    ]
    api.save_documents(preview_data, "/tmp/out")
    called_args = mock_split_and_save.call_args[0]
    assert called_args[3] == "Акт 2026"

def test_fallback_naming_empty_name(mocker):
    api = Api()
    mocker.patch('os.makedirs')
    mock_split_and_save = mocker.patch.object(api.pdf_processor, 'split_and_save', return_value='/tmp/mock.pdf')
    mocker.patch.object(api, 'send_status')

    preview_data = [
        {
            "original_file": "/tmp/orig.pdf",
            "start_page": 5,
            "end_page": 5,
            "short_name": "Ошибка*",
            "date": ""
        }
    ]
    api.save_documents(preview_data, "/tmp/out")
    called_args = mock_split_and_save.call_args[0]
    # If it becomes empty, it should fallback to "Документ_стр_5"
    assert called_args[3] == "Документ_стр_5"

def test_process_files_mocked_llm(mocker):
    api = Api()
    mocker.patch.object(api, 'send_status')
    
    # Mock model check so process_files proceeds
    mocker.patch.object(api.model_manager, 'get_active_model_type', return_value='fast')
    mocker.patch.object(api.model_manager, 'check_model_exists', return_value=True)
    mocker.patch.object(api.model_manager, 'get_model_path', return_value='/tmp/model')
    
    # Mock LLMHandler so we don't actually load a model
    mock_llm = mocker.MagicMock()
    # Mock the return value of analyze_text
    mock_llm.analyze_text.return_value = {
        'parties': 'Party A _ Party B',
        'short_name': 'Договор',
        'full_name': 'Договор подряда',
        'date': '01.01.2025',
        'confidence_score': 95
    }
    
    # Patch the LLMHandler class in the module where Api imports it
    mocker.patch('backend.api.LLMHandler', return_value=mock_llm)
    
    # Mock PDF processor
    mocker.patch.object(api.pdf_processor, 'extract_text', return_value=[
        {'page_num': 1, 'text': 'ДОГОВОР ПОДРЯДА №1\\nг. Москва'},
        {'page_num': 2, 'text': 'АКТ ВЫПОЛНЕННЫХ РАБОТ\\nг. Москва'}
    ])
    
    # Patch image generation to prevent fitz errors
    mocker.patch('fitz.open')
    
    results = api.process_files(['/tmp/dummy.pdf'])
    
    # Since 'АКТ' is on page 2, is_new_document_start should trigger and split it
    assert len(results) == 2
    assert results[0]['start_page'] == 1
    assert results[0]['end_page'] == 1
    assert results[0]['short_name'] == 'Договор'
    
    assert results[1]['start_page'] == 2
    assert results[1]['end_page'] == 2
    assert results[1]['short_name'] == 'Договор' # Mock always returns 'Договор'
