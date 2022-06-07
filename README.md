# MIBI scanning GUI

## Aim
The aim of this project is to assist MIBI operators with field of view (FoV) selection based on reference images.

## Software Requirements
You can run HE_GUI from the command line using Python 3.7 plus all required libraries (see [environment.yml](https://github.com/WEHI-labatlab/HE_GUI/blob/main/environment.yml)).

However, it's more convenient to use Miniconda - a small bootstrap version of Anaconda - instead.

If you have not installed Miniconda yet, you can find it here:
> https://docs.conda.io/en/latest/miniconda.html

## Installation with Miniconda
Copy this repository onto your local device (extract the ZIP archive if necessary) and navigate to the `HE_GUI` folder.

Run Miniconda from the Start Menu and create a new environment for heGUI:
```
conda env create -n heGUI -f environment.yml
```
Now run heGUI using the newly created Anaconda environment:
```
conda run -n heGUI .\heGUI\main.pyw
```
