import os

IP = '0.0.0.0' 
PORT = 1233
path_model_wb = os.path.join(
    os.getcwd(), "models", "model_wb.pkl"
)
path_model_lamoda = os.path.join(
    os.getcwd(), "models", "model_lamoda.pkl"
)
path_model_mustapp = os.path.join(
    os.getcwd(), "models", "model_mustapp.pkl"
)
path_model_both = os.path.join(
    os.getcwd(), "models", "model_wb_and_lamoda.pkl"
)