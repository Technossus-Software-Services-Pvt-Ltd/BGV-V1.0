import os
import tarfile
import urllib.request

models = {
    "det/en/en_PP-OCRv3_det_infer": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar",
    "rec/en/en_PP-OCRv4_rec_infer": "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar",
    "cls/ch_ppocr_mobile_v2.0_cls_infer": "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar"
}

# Use the appuser's home directory (in docker, it's /home/appuser)
base_dir = os.path.expanduser("~/.paddleocr/whl")
tar_file_name_list = [".pdiparams", ".pdiparams.info", ".pdmodel"]

for rel_path, url in models.items():
    model_storage_directory = os.path.join(base_dir, rel_path)
    os.makedirs(model_storage_directory, exist_ok=True)
    
    # Check if already downloaded/extracted
    param_path = os.path.join(model_storage_directory, "inference.pdiparams")
    model_path = os.path.join(model_storage_directory, "inference.pdmodel")
    if os.path.exists(param_path) and os.path.exists(model_path):
        print(f"Model {rel_path} already exists. Skipping.")
        continue

    tmp_path = os.path.join(model_storage_directory, url.split("/")[-1])
    print(f"Downloading {url} to {tmp_path}...")
    
    try:
        # Download the file
        urllib.request.urlretrieve(url, tmp_path)
        print(f"Extracting {tmp_path} to {model_storage_directory}...")
        
        # Extract files following PaddleOCR logic
        with tarfile.open(tmp_path, "r") as tarObj:
            for member in tarObj.getmembers():
                filename = None
                for suffix in tar_file_name_list:
                    if member.name.endswith(suffix):
                        filename = "inference" + suffix
                if filename is None:
                    continue
                file_data = tarObj.extractfile(member)
                if file_data is not None:
                    with open(os.path.join(model_storage_directory, filename), "wb") as f:
                        f.write(file_data.read())
                    
        print(f"Extraction complete. Cleaning up {tmp_path}...")
        os.remove(tmp_path)
    except Exception as e:
        print(f"Error processing {rel_path}: {e}")
        # Re-raise so the docker build fails if download fails
        raise e

print("All models downloaded and extracted successfully.")
