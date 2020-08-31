/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/

package app.input;

import java.net.URL;
import java.util.ResourceBundle;
import com.consts.Constants.EnumStep;
import core.app.input.InputController;
import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Label;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.VBox;

public class InputBandsPPController extends InputController{

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private VBox vboxPdos;

    @FXML
    private ToggleButton toggleProjwfc;

    @FXML
    private CheckBox checkProjwfc;

    @FXML
    private Button infoProjwfc;

    @FXML
    private Label statusInfo;
    
    
	public InputBandsPPController(MainClass mc) {
		super(mc, EnumStep.BANDS);//must link to bands because agent is there
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo

		initParameterSet(toggleProjwfc, "boolProjwfc", "ON", "OFF", checkProjwfc, infoProjwfc, checkResetAll);

		//checkAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				checkProjwfc.setSelected(newValue);
			}
		});
	}

}

