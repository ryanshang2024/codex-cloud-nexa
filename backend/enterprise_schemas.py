from typing import Literal
from pydantic import Field, model_validator
from .schemas import Input

class Login(Input):
    tenant_id:str=Field(min_length=1,max_length=200)
    user_id:str=Field(min_length=1,max_length=200)
    password:str=Field(min_length=1,max_length=500)
class UserInput(Input):
    user_id:str=Field(min_length=1,max_length=200,pattern=r'^[a-zA-Z0-9_:-]+$')
    display_name:str=Field(min_length=1,max_length=100)
    role:Literal['super_admin','manager','employee']
    password:str=Field(min_length=12,max_length=200)
class UserState(Input):
    active:bool
    role:Literal['super_admin','manager','employee']
    reason:str=Field(min_length=10,max_length=1000)
class Grant(Input):
    permission:str
    enabled:bool
    provinces:list[Literal['QC','ON']]=Field(default_factory=list,max_length=2)
    reason:str=Field(min_length=10,max_length=1000)
class Assignment(Input):
    account_id:str
    user_id:str
    task_id:str|None=None
    contact_id:str|None=None
    allowed_fields:list[Literal['name','province','website','email']]=Field(default_factory=lambda:['name','province'])
    instructions:str=Field(min_length=1,max_length=2000)
class WorkUpdate(Input):
    status:Literal['open','done','cancelled']
    reason:str=Field(min_length=1,max_length=1000)
class Note(Input):
    text:str=Field(min_length=1,max_length=4000)
class RoleLimits(Input):
    requests:int=Field(ge=0,le=10000)
    tokens:int=Field(ge=0,le=10000000)
    voice_seconds:int=Field(ge=0,le=86400)
    source_calls:int=Field(ge=0,le=10000)
    concurrency:int=Field(ge=0,le=20)
    max_task_cost_micros:int=Field(ge=0,le=100000000)
    max_leads:int=Field(ge=0,le=200)
    max_retries:int=Field(ge=0,le=3)
    job_concurrency:int=Field(ge=0,le=20)
class AIPolicy(Input):
    monthly_budget_micros:int=Field(ge=0,le=100000000000)
    warning_percent:int=Field(ge=1,le=100)
    monthly_tokens:int=Field(ge=0,le=1000000000)
    monthly_voice_seconds:int=Field(ge=0,le=10000000)
    monthly_source_calls:int=Field(ge=0,le=10000000)
    concurrency:int=Field(ge=0,le=20)
    paused:bool
    model_enabled:bool
    voice_enabled:bool
    model:Literal['gpt-4.1-mini','gpt-4.1','gpt-4o-mini']
    pricing_reviewed:bool
    input_micros_per_million:int=Field(ge=0,le=1000000000)
    output_micros_per_million:int=Field(ge=0,le=1000000000)
    voice_micros_per_minute:int=Field(ge=0,le=100000000)
    roles:dict[Literal['employee','manager','super_admin','service'],RoleLimits]
    @model_validator(mode='after')
    def complete(self):
        if set(self.roles)!={'employee','manager','super_admin','service'} or self.roles['employee'].max_leads!=0:
            raise ValueError('All roles required; employee max_leads is permanently zero')
        return self
class Quota(Input):
    requests:int=Field(ge=0,le=10000)
    tokens:int=Field(ge=0,le=10000000)
    voice_seconds:int=Field(ge=0,le=86400)
    concurrency:int=Field(ge=0,le=20)
    reason:str=Field(min_length=10,max_length=1000)
class Assistant(Input):
    action:Literal['task_query','work_summary','followup_draft','voice_record','lead_research','company_analysis','export']
    task_id:str|None=None
    prompt:str=Field(default='',max_length=4000)
    use_ai:bool=False
    idempotency_key:str=Field(min_length=1,max_length=200)
