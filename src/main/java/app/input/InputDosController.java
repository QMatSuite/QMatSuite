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
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumSummation;
import com.consts.Constants.EnumUnitEnergy;
import agent.InputAgentDos;
import core.app.input.InputController;
import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.GridPane;

public class InputDosController extends InputController {

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private Label emaxLabel;

    @FXML
    private Label eminLabel;

    @FXML
    public TextField textEmax;

    @FXML
    public ComboBox<EnumUnitEnergy> unitEminCombo;

    @FXML
    public TextField textEmin;

    @FXML
    private Label unitEmax;

    @FXML
    private Button infoEmax;

    @FXML
    private Button infoEmin;

    @FXML
    private Label edeltaLabel;

    @FXML
    private Button infoEstep;

    @FXML
    public TextField textEstep;

    @FXML
    private Label unitEstep;

    @FXML
    private Label broadLabel;

    @FXML
    private Button infoSmearing;

    @FXML
    private ComboBox<EnumSmearing> comboSmearing;

    @FXML
    private Label broadWidthLabel;

    @FXML
    private TextField textDegauss;

    @FXML
    private Label unitDegauss;

    @FXML
    private Button infoDegauss;

    @FXML
    private CheckBox checkEmax;

    @FXML
    private CheckBox checkEmin;

    @FXML
    private CheckBox checkEstep;

    @FXML
    private CheckBox checkSmearing;

    @FXML
    private CheckBox checkDegauss;

    @FXML
    private CheckBox checkSummation;

    @FXML
    private ComboBox<EnumSummation> comboSummation;

    @FXML
    private CheckBox checkShowAdvanced;

    @FXML
    private Button infoSummation;
    
    @FXML
    private Label statusInfo;
    
    @FXML
    private GridPane panelAdvanced;
    
	public InputDosController(MainClass mc) {
		super(mc, EnumStep.DOS);
	}
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
				
		//new
		
		initDoubleParameterSet(textEmax, "emax", EnumNumCondition.no, "Automated", checkEmax, infoEmax, checkResetAll);
		initDoubleParameterSet(textEmin, "emin", EnumNumCondition.no, "Automated", checkEmin, infoEmin, checkResetAll);
		
		unitEmax.textProperty().bind(unitEminCombo.valueProperty().asString());
		unitEstep.textProperty().bind(unitEminCombo.valueProperty().asString());
		unitDegauss.textProperty().bind(unitEminCombo.valueProperty().asString());
		
		checkEstep.setDisable(true);
		setDoubleFieldListener(textEstep, "estep",EnumNumCondition.no);
		
		checkShowAdvanced.selectedProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			InputAgentDos iDos = (InputAgentDos) mainClass.projectManager.getStepAgent(EnumStep.DOS);
			iDos.setAdvanced = newValue;
			panelAdvanced.setVisible(newValue);
		});
		
		//advanced
		checkShowAdvanced.setSelected(false);panelAdvanced.setVisible(false);
		setComboListener(unitEminCombo, EnumUnitEnergy.values(), "energyUnit");
		initParameterSet(comboSummation, "enumSummation", EnumSummation.values(), false, checkSummation, infoSummation, checkResetAll);
		//0,1,-1,-99 for input file
		initParameterSet(comboSmearing, "enumSmearing", EnumSmearing.values(), false, checkSmearing, infoSmearing, checkResetAll);
		initDoubleParameterSet(textDegauss, "degauss", EnumNumCondition.nonNegative, "None", checkDegauss, infoDegauss, checkResetAll);

		//resetAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				checkEmax.setSelected(newValue);
				checkEmin.setSelected(newValue);
				//checkEstep.setSelected(newValue);
//				if(checkShowAdvanced.isSelected()) {
//					checkSummation.setSelected(newValue);
//					checkSmearing.setSelected(newValue);
//					checkDegauss.setSelected(newValue);
//				}
				checkShowAdvanced.setSelected(!newValue);
			}
		});
	}

	public void loadProjectParameters() {
		super.loadProjectParameters();

		InputAgentDos iDos = (InputAgentDos) mainClass.projectManager.getStepAgent(EnumStep.DOS);
		if (iDos!=null) {
			checkShowAdvanced.setSelected(iDos.setAdvanced);
			setCombo(unitEminCombo, iDos.energyUnit);
			setField(textEstep, iDos.estep);	
		}
	}

}




