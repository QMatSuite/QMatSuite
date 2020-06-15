package com.error;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import main.Main;

public interface ShowAlert {
	static void showAlert(AlertType at, String headerText, String contentText) {
		if(!Main.isTestMode()) {
			Alert alert1 = new Alert(at);
			alert1.setHeaderText(headerText);
			alert1.setContentText(contentText);
			alert1.showAndWait();
		}
	}
}
