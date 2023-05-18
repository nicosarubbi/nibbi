from pydantic import BaseModel


def serialize(serializer_class: type[BaseModel], _obj=None, **fields) -> BaseModel:  # noqa
    schema = serializer_class.__fields__
    data = {}
    for field_name, detail in schema.items():
        if field_name in fields:
            value = fields[field_name]    
            if callable(value):
                value = value(_obj)
        elif hasattr(_obj, field_name):
            value = getattr(_obj, field_name)
        elif isinstance(_obj, dict) and field_name in _obj:
            value = _obj[field_name]
        else:
            continue
        if isinstance(detail.type_, type) and issubclass(detail.type_, BaseModel):
            prefix = f"{field_name}__"
            sub_fields = {key.lstrip(prefix): value for key, value in fields.items() if key.startswith(prefix)}
            type_ = detail.type_
            outer_type_ = detail.outer_type_
            if outer_type_ == list[type_]:
                if value:
                    value = [serialize(type_, item, **sub_fields) for item in value]
            elif outer_type_ == dict[str, type_]:
                if isinstance(value, dict):
                    value = { key: serialize(type_, item, **sub_fields) for key, item in value.items()}
            else:
                value = serialize(detail.type_, value, **sub_fields)
        data[field_name] = value
    return serializer_class(**data)
