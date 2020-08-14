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
package app.menus.settingtabs;


import java.net.URL;
import java.util.ResourceBundle;

import com.programconst.ProgrammingConstsQE;

import core.com.error.ShowAlert;
import core.com.programconst.ProgrammingConsts;
import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.layout.AnchorPane;

public class GeneralSettingController implements Initializable, SettingTabController{

	@FXML
    private AnchorPane acp;

    @FXML
    private TextField textMaxLines;

    @FXML
    private Label labelMaxLines;

    private MainClass mainClass;
    
    public GeneralSettingController(MainClass mc) {
    	mainClass = mc;
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		loadValues();
	}
	public void loadValues() {
		labelMaxLines.setText(Integer.toString(ProgrammingConsts.maxLinesShownInText));
		textMaxLines.setText(labelMaxLines.getText());
	}
	public void saveChanges() {

		try {
			Integer intTmp = Integer.valueOf(textMaxLines.getText());
			if(intTmp==null) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Null input for max lines.");
			}
			else if(intTmp<=0){
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Input must be positive integer for max lines.");
			}
			else {
				ProgrammingConsts.maxLinesShownInText = intTmp;
			}
		}
		catch(Exception e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Input must be integer for max lines.");
		}

		loadValues();
	}
}