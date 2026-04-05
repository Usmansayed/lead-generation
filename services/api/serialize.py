"""JSON-serialize MongoDB documents (ObjectId, datetime)."""
from datetime import datetime
from bson import ObjectId

def serialize_doc(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(x) for x in doc]
    if not isinstance(doc, dict):
        if isinstance(doc, datetime):
            return doc.isoformat() + "Z"
        if isinstance(doc, ObjectId):
            return str(doc)
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat() + "Z"
        elif isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, dict):
            out[k] = serialize_doc(v)
        elif isinstance(v, list):
            out[k] = serialize_doc(v)
        else:
            out[k] = v
    return out
