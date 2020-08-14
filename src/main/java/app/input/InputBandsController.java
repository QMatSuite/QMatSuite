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
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;

import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.VBox;

public class InputBandsController extends InputK{
	
	@FXML
    private Label nbandLabel;

    @FXML
    private TextField textNBands;

    @FXML
    private Button infoNBands;

    @FXML
    private CheckBox checkNBands;
    
    @FXML
    private VBox vboxKpath;
    
	public InputBandsController (MainClass mc) {
		super(mc, EnumStep.BANDS);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		super.initialize(location, resources);
		setChild(vboxKpath);
		
		initIntegerParameterSet(textNBands, "intNBands", EnumNumCondition.positive, "Automated", checkNBands, infoNBands, null);
	}
}
