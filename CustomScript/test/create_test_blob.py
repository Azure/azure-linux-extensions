import blob
import blob_mooncake
import customscript as cs
from azure.storage import BlobService

def create_blob(blob, txt):
    uri = blob.uri
    host_base = cs.get_host_base_from_uri(uri)
    service = BlobService(blob.name,
                          blob.key,
                          host_base=host_base)
    
    container_name = cs.get_container_name_from_uri(uri)
    blob_name = cs.get_blob_name_from_uri(uri)
    service.put_block_blob_from_text(container_name,
                                     blob_name,
                                     txt)

if __name__ == "__main__":
    create_blob(blob, "public azure\n") 
    create_blob(blob_mooncake, "mooncake\n") 
