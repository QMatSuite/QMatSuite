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
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.GridPane;
import main.MainClass;

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
    private TextField textEmax;

    @FXML
    private ComboBox<EnumUnitEnergy> unitEmaxCombo;

    @FXML
    private TextField textEmin;

    @FXML
    private Label unitEmin;

    @FXML
    private Button infoEmax;

    @FXML
    private Button infoEmin;

    @FXML
    private Label edeltaLabel;

    @FXML
    private Button infoEstep;

    @FXML
    private TextField textEstep;

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
		super(mc);
	}
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
				
		setDoubleFieldListener(textEmax, "emax",EnumNumCondition.no,EnumStep.DOS);
		setDoubleFieldListener(textEmin, "emin",EnumNumCondition.no,EnumStep.DOS);
		setDoubleFieldListener(textEstep, "estep",EnumNumCondition.no,EnumStep.DOS);
		setComboListener(unitEmaxCombo, EnumUnitEnergy.values(), "energyUnit", EnumStep.DOS);
		
		setComboListener(comboSummation, EnumSummation.values(), "enumSummation", EnumStep.DOS);
		setComboListener(comboSmearing, EnumSmearing.values(), "enumSmearing", EnumStep.DOS);//0,1,-1,-99 for input file
		setDoubleFieldListener(textDegauss, "degauss",EnumNumCondition.nonNegative,EnumStep.DOS);
		
		unitEmin.textProperty().bind(unitEmaxCombo.valueProperty().asString());
		unitEstep.textProperty().bind(unitEmaxCombo.valueProperty().asString());
		unitDegauss.textProperty().bind(unitEmaxCombo.valueProperty().asString());
		
		checkShowAdvanced.selectedProperty().addListener((observable, oldValue, newValue) -> {
			if(newValue==null) return;
			InputAgentDos iDos = (InputAgentDos) mainClass.projectManager.getStepAgent(EnumStep.DOS);
			iDos.setAdvanced = newValue;
			panelAdvanced.setVisible(newValue);
		});
		checkShowAdvanced.setSelected(false);panelAdvanced.setVisible(false);
		
		
		//reset checkBoxes
		resetTextFieldDoubleListener(checkEmax, textEmax, "emax", EnumStep.DOS, checkResetAll,"Automated");
		resetTextFieldDoubleListener(checkEmin, textEmin, "emin", EnumStep.DOS, checkResetAll,"Automated");

		checkEstep.setDisable(true);
		
		//advanced
		resetComboBoxListener(checkSummation, comboSummation, "enumSummation", EnumStep.DOS, checkResetAll);
		resetComboBoxListener(checkSmearing, comboSmearing, "enumSmearing", EnumStep.DOS, checkResetAll);
		resetTextFieldDoubleListener(checkDegauss, textDegauss, "degauss", EnumStep.DOS, checkResetAll,"None");
		
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				checkEmax.setSelected(newValue);
				checkEmin.setSelected(newValue);
				//checkEstep.setSelected(newValue);
				if(checkShowAdvanced.isSelected()) {
					checkSummation.setSelected(newValue);
					checkSmearing.setSelected(newValue);
					checkDegauss.setSelected(newValue);
				}
			}
		});
	}

	public void loadProjectParameters() {
		if (!comboSummation.getItems().isEmpty()) {
    		InputAgentDos iDos = (InputAgentDos) mainClass.projectManager.getStepAgent(EnumStep.DOS);
    		if (iDos!=null) {
    			checkShowAdvanced.setSelected(iDos.setAdvanced);
    			
    			setField(textEmax, iDos.emax);
    			setField(textEmin, iDos.emin);
    			setField(textEstep, iDos.estep);
    			setCombo(unitEmaxCombo, iDos.energyUnit);
    			setCombo(comboSummation, iDos.enumSummation);
    			
    			setCombo(comboSmearing, iDos.enumSmearing);
    			setField(textDegauss, iDos.degauss);
    			
    			
    			//load default checkBoxes
    			checkEmax.setSelected(!iDos.emax.isEnabled());
    			checkEmin.setSelected(!iDos.emin.isEnabled());
    			checkEstep.setSelected(!iDos.estep.isEnabled());//just for completeness. No use here
				checkSummation.setSelected(!iDos.enumSummation.isEnabled());
				checkSmearing.setSelected(!iDos.enumSmearing.isEnabled());
				checkDegauss.setSelected(!iDos.degauss.isEnabled());

    			
    		}
    	}
	}

}




