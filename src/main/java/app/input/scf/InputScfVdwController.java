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

package app.input.scf;

import java.net.URL;
import java.util.ResourceBundle;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumVdw;
import app.input.InputController;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import main.MainClass;

public class InputScfVdwController extends InputController{

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private ComboBox<EnumVdw> comboVdw;
    
    @FXML
    private CheckBox checkVdw;

    @FXML
    private Button infoVdw;

    @FXML
    private Label statusInfo;
    
    
	public InputScfVdwController(MainClass mc) {
		super(mc, EnumStep.SCF);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		initParameterSet(comboVdw, "enumVdw", EnumVdw.values(), 
				checkVdw, infoVdw, checkResetAll);
		
		//checkResetAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				checkVdw.setSelected(newValue);
				allDefault = newValue;
			}
		});
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();
	}

}
	






