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

public class InputPdosController extends InputController{

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private ToggleButton togglePdos;

    @FXML
    private CheckBox checkPdos;

    @FXML
    private Button infoPdos;

    @FXML
    private Label nbandLabel;

    @FXML
    private Label unitdE;

    @FXML
    private Label labeldE;

    @FXML
    private Label unitEmin;

    @FXML
    private Label labelEmin;

    @FXML
    private Label unitEmax;

    @FXML
    private Label labelEmax;

    @FXML
    private ToggleButton toggleOverlaps;

    @FXML
    private CheckBox checkOverlaps;

    @FXML
    private Button infoOverlaps;

    @FXML
    private VBox vboxPdos;
    
    @FXML
    private Label statusInfo;
    
    private InputDosController contDos;
    
	public InputPdosController(MainClass mc, InputDosController contDos) {
		super(mc, EnumStep.DOS); //must use DOS (rather than PDOS) here because we use InputAgentDos to store the information
		this.contDos = contDos;
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		initParameterSet(toggleOverlaps, "boolLwrite", "ON", "OFF", checkOverlaps, infoOverlaps, checkResetAll);
		initParameterSet(togglePdos, "boolPdos", "ON", "OFF", checkPdos, infoPdos, checkResetAll);
		
		vboxPdos.visibleProperty().bind(togglePdos.selectedProperty());
		labeldE.textProperty().bind(contDos.textEstep.textProperty());
		labelEmin.textProperty().bind(contDos.textEmin.textProperty());
		labelEmax.textProperty().bind(contDos.textEmax.textProperty());
		unitdE.textProperty().bind(contDos.unitEminCombo.valueProperty().asString());
		unitEmin.textProperty().bind(unitdE.textProperty());
		unitEmax.textProperty().bind(unitdE.textProperty());
		
		//checkAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				checkPdos.setSelected(newValue);
				checkOverlaps.setSelected(newValue);
			}
		});
	}

}

