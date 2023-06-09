# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'cosik.ui'
#
# Created by: PyQt5 UI code generator 5.15.4
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
import numpy as np
import matplotlib.pyplot as plt
import keras.utils as image
from keras.preprocessing.image import ImageDataGenerator
from keras.applications.vgg16 import VGG16
from keras.layers import Dense, Dropout, Flatten
from keras.models import Model, load_model
from keras.optimizers import Adam
import tensorflow as tf
import cv2
from pathlib import Path
import os
import random
import shutil
import math
import json

img_width, img_height = 150, 150

class_labels = ['RottenMango', 'FreshOrange', 'FreshCucumber', 'RottenTomato', 'FreshTomato', 'RottenStrawberry', 'RottenBellpepper', 'RottenOrange', 'FreshApple', 'RottenPotato', 'RottenCarrot', 'RottenBanana', 'FreshPotato', 'RottenApple', 'FreshBellpepper', 'FreshCarrot', 'RottenCucumber', 'FreshStrawberry', 'FreshMango', 'FreshBanana']
with open('FruitsAndVegetables_GUI\config.json') as config_file:
    config = json.load(config_file)


class GradCAM:
    def __init__(self, model, classIdx, layerName=None):
        self.model = model
        self.classIdx = classIdx
        self.layerName = layerName
        if self.layerName is None:
            self.layerName = self.find_target_layer()

    def find_target_layer(self):
        for layer in reversed(self.model.layers):
            if len(layer.output_shape) == 4:
                return layer.name

        raise ValueError("No 4D layers found!")

    def compute_heatmap(self, image, eps=1e-8):
        gradModel = Model(inputs=[self.model.inputs],
                          outputs=[self.model.get_layer(self.layerName).output, self.model.output])
        with tf.GradientTape() as tape:
            inputs = tf.cast(image, tf.float32)
            (convOutputs, predictions) = gradModel(inputs)
            loss = predictions[:, self.classIdx]

        grads = tape.gradient(loss, convOutputs)
        castConvOutputs = tf.cast(convOutputs > 0, "float32")
        castGrads = tf.cast(grads > 0, "float32")
        guidedGrads = castConvOutputs * castGrads * grads
        convOutputs = convOutputs[0]
        guidedGrads = guidedGrads[0]

        weights = tf.reduce_mean(guidedGrads, axis=(0, 1))
        cam = tf.reduce_sum(tf.multiply(weights, convOutputs), axis=-1)

        (w, h) = (image.shape[2], image.shape[1])
        heatmap = cv2.resize(cam.numpy(), (w, h))

        numer = heatmap - np.min(heatmap)
        denom = (heatmap.max() - heatmap.min()) + eps
        heatmap = numer / denom
        heatmap = (heatmap * 255).astype("uint8")

        return heatmap

    def overlay_heatmap(self, heatmap, image, alpha=0.5, colormap=cv2.COLORMAP_VIRIDIS):
        heatmap = cv2.applyColorMap(heatmap, colormap)
        output = cv2.addWeighted(image, alpha, heatmap, 1 - alpha, 0)

        return (heatmap, output)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox.setGeometry(QtCore.QRect(40, 80, 111, 22))
        self.comboBox.setObjectName("comboBox")
        self.comboBox.addItems(["VGG", "ResNet"])

        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(40, 60, 161, 16))
        self.label.setObjectName("label")

        self.comboBox2 = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox2.setGeometry(QtCore.QRect(200, 80, 111, 22))
        self.comboBox2.setObjectName("comboBox")
        self.comboBox2.addItems(class_labels)

        self.label2 = QtWidgets.QLabel(self.centralwidget)
        self.label2.setGeometry(QtCore.QRect(200, 60, 161, 16))
        self.label2.setObjectName("label2")

        self.start_button = QtWidgets.QPushButton(self.centralwidget)
        self.start_button.setGeometry(QtCore.QRect(40, 120, 113, 22))
        self.start_button.setObjectName("button_start")
        self.start_button.clicked.connect(self.start_algorithm)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 26))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.label.setText(_translate("MainWindow", "Wybrana sieć"))
        self.label2.setText(_translate("MainWindow", "Produkt"))
        self.start_button.setText(_translate("MainWindow", "Start"))

    def predict_photo(self, photo, n=3):
        """
        Predicts label of given photo. If file_name is None,
        random photo is chosen from folder_name directory

        Returns list of tuples of top n guesses.
        """
        prediction = np.array(self.model(photo, training=False))
        idxs = prediction.argsort()[0][::-1][:n]
        preds = [(class_labels[idx], prediction[0][idx]) for idx in idxs]
        return preds


    def plot_heatmap(self, image_path, class_label):
        """
        Plots 6 predictions with heatmap from given folders,
        if folders are None, chooses them randomly
        if files are not None it should contain paths to custom photos.
        """
        class_idx = class_labels.index(class_label)
        fig, axs = plt.subplots(1, 1)
        fig.set_size_inches(14, 12)
        img_orig = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        img_orig = cv2.cvtColor(img_orig, cv2.COLOR_BGR2RGB)
        img_orig = cv2.resize(img_orig, (img_width, img_height))


        img = image.load_img(image_path, target_size=(img_width, img_height))
        img = image.img_to_array(img)
        img = np.expand_dims(img, axis=0)
        img = img / 255.0

        preds = self.predict_photo(img)
        gradcam = GradCAM(self.model, class_idx)
        heatmap = gradcam.compute_heatmap(img)
        heatmap = cv2.resize(heatmap, (img_width, img_height))
        (heatmap, output) = gradcam.overlay_heatmap(heatmap, img_orig, alpha=0.5)

        axs.imshow(output)
        axs.set_title(f"Class: {class_labels[class_idx]}\n "
                                     f"{preds[0][0]}: {np.round(preds[0][1] * 100, 2)}%\n"
                                     f"{preds[1][0]}: {np.round(preds[1][1] * 100, 2)}%\n"
                                     f"{preds[2][0]}: {np.round(preds[2][1] * 100, 2)}%")
        plt.show()

    def start_algorithm(self):
        model_name = self.comboBox.currentText()
        self.model = load_model(config[model_name])
        product = self.comboBox2.currentText()
        data = QFileDialog.getOpenFileName(
            parent=None,
            caption="Select a data file",
            directory=os.getcwd()
        )
        if data[0] != "":
            self.plot_heatmap(data[0], product)
