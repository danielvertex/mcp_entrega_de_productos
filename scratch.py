from pydantic import BaseModel, Field
from prefab_ui.components import Form

class A(BaseModel):
    x: float = Field(json_schema_extra={"step": "any"})
    y: float = Field(multiple_of=0.0000001)
    z: float = Field()

f = Form.from_model(A, submit_label="ok", on_submit=None)
# print(f.to_html())
# Wait, prefab_ui components serialize to dict/JSON often.
import json
print(json.dumps(f.model_dump(), indent=2))
