"""Exercise the real ADK Runner integration with only the model transport replaced."""
import asyncio
import pytest
from types import SimpleNamespace
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from hubrecover.application.ai import BoundedAI, AIProviderFailure
from hubrecover.application.service import RecoveryService
from hubrecover.domain.claims import EditProposal


@pytest.mark.parametrize('provider_error',[None,'RESOURCE_EXHAUSTED'])
def test_real_adk_root_configuration_accepts_schema_and_calls_model_once(tmp_path,monkeypatch,provider_error):
    import hubrecover.application.ai as module
    calls=[]
    class Transport(BaseLlm):
        async def generate_content_async(self,llm_request,stream=False):
            calls.append(llm_request)
            if provider_error:
                yield LlmResponse(error_code=provider_error,error_message='Synthetic transport error')
                return
            yield LlmResponse(content=types.Content(role='model',parts=[types.Part(text='{"kind":"CLARIFY","clarification":"AMBIGUOUS_REFERENCE"}')]))
    class Client:
        def __init__(self,**kwargs): self.aio=SimpleNamespace(models=self,aclose=self.aclose)
        async def count_tokens(self,**kwargs): return SimpleNamespace(total_tokens=500)
        async def aclose(self): pass
        def close(self): pass
    monkeypatch.setenv('GOOGLE_API_KEY','synthetic-test-key')
    monkeypatch.setenv('HUBRECOVER_GEMINI_MODEL','synthetic-test-model')
    monkeypatch.setattr(module.genai,'Client',Client)
    monkeypatch.setattr(module,'Gemini',lambda model,client:Transport(model=model))
    ai=BoundedAI(RecoveryService(tmp_path/'ledger.sqlite'))
    if provider_error:
        with pytest.raises(AIProviderFailure) as exc:
            asyncio.run(ai.generate(EditProposal,dict(text='Protect that one.'),'edit'))
        assert exc.value.code==provider_error
    else:
        result=asyncio.run(ai.generate(EditProposal,dict(text='Protect that one.'),'edit'))
        assert result.kind=='CLARIFY'
    assert len(calls)==1
    assert not calls[0].tools_dict
    assert calls[0].config.response_schema is None
    assert calls[0].config.response_json_schema['additionalProperties'] is False
