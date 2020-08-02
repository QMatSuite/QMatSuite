/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.error;

import java.time.Duration;
import java.time.Instant;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import main.MainApplication;

public class ShowAlert {
	private ShowAlert() {}
	
	private static boolean boolShow = true;
	private static Instant startTime = Instant.now();  
	
	public static void showAlert(AlertType at, String headerText, String contentText) {
		if(!MainApplication.isTestMode()) {
			Instant endTime = Instant.now();
			Duration timeElapsed = Duration.between(startTime, endTime); 
			if(timeElapsed.toMillis()<100) {
				//too many alerts shown within a short time. Suppress alerts
				if(boolShow) {
					Alert alert1 = new Alert(at);
					alert1.setHeaderText("Multiple warnings. Further alerts suppressed tempararily.");
					alert1.setContentText(contentText);
					alert1.showAndWait();
				}
				boolShow=false;
			}
			else {
				boolShow = true;
				Alert alert1 = new Alert(at);
				alert1.setHeaderText(headerText);
				alert1.setContentText(contentText);
				alert1.showAndWait();
			}
			startTime = Instant.now();
		}
	}
}
