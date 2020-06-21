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
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import main.MainClass;
import agent.InputAgentScf;
import app.input.InputController;
import com.consts.Constants.EnumMixingMode;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitEnergy;

public class InputScfStandardController extends InputController{

    @FXML private CheckBox checkResetAll;

    @FXML private Button infoResetAll;

    @FXML
    private ToggleButton restartToggle,
    forceToggle,
    stressToggle;

    @FXML
    private TextField ecutwfcField;

    @FXML
    private ComboBox<EnumUnitEnergy> ecutwfcUnit;

    @FXML
    private TextField ecutrhoField,
    maxStepField;

    @FXML
    private Label ecutrhoUnit,
    statusInfo;

    @FXML
    private TextField convField;

    @FXML
    private Label convUnit;

    @FXML
    private ComboBox<EnumMixingMode> mixingModeCombo;

    @FXML
    private TextField mixingField;

    @FXML
    private TextField kxField,
    kyField,
    kzField;

    @FXML
    private ComboBox<EnumOccupations> occupCombo;

    @FXML
    private ComboBox<EnumSmearing> smearCombo;

    @FXML
    private TextField gaussField;

    @FXML
    private Label gaussUnit;

    @FXML private Button infoRestart,
    infoForce,
    infoStress,
    infoEcutwfc,
    infoEcutRho,
    infoMaxstep,
    infoConv;
    
    @FXML private Button infoMixMode,
    infoMixBeta,
    infoK,
    infoOccup,
    infoSmearing,
    infoGauss;

    @FXML private CheckBox checkRestart,
    checkForce,
    checkStress,
    checkEcutwfc,
    checkEcutrho,
    checkMaxStep;
    
    @FXML private CheckBox checkConv,
    checkMixMode,
    checkMixBeta,
    checkK,
    checkOccup,
    checkSmear,
    checkGauss;
    
	
	public InputScfStandardController(MainClass mc) {
		super(mc, EnumStep.SCF);
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		initialize();
    }
    public void initialize(){
    	if (occupCombo.getItems().isEmpty()) {
    		//new
    		checkEcutwfc.setDisable(true);
    		ecutwfcField.textProperty().addListener((observable, oldValue, newValue) -> {
    			InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
    			if (ia==null) return;
    			Double tmp = str2double(newValue);
				if (tmp!=null) {
					if(tmp<=0) {statusInfo.setText("Must be positive!");return;}
				
    				statusInfo.setText("");
    				ia.ecutWfc.setValue(tmp);
    				if (checkEcutrho.isSelected()) {
    					ecutrhoField.setText(String.valueOf(tmp*4.0));//because of this, cannot separate into two listeners
    				}
				}
    		});
    		checkEcutrho.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf==null || newValue==null) return;
				if (newValue) {
					ecutrhoField.setDisable(true);
					if(!iScf.ecutWfc.isNull()){
						iScf.ecutRho.setValue(iScf.ecutWfc.getValue()*4.0);
						ecutrhoField.setText(String.valueOf(iScf.ecutWfc.getValue()*4.0));
					}
					iScf.ecutRho.setEnabled(false);
				}
				else {iScf.ecutRho.setEnabled(true);ecutrhoField.setDisable(false);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
			});

    		initParameterSet(restartToggle, "boolRestart", "restart", "from scratch", checkRestart, infoRestart, "infoRestart", checkResetAll);
    		initParameterSet(forceToggle, "boolForce", "on", "off", checkForce, infoForce, "infoForce", checkResetAll);
    		initParameterSet(stressToggle, "boolStress", "on", "off", checkStress, infoStress, checkResetAll);
    		
    		initParameterSet(mixingModeCombo, "enumMixing", EnumMixingMode.values(), checkMixMode, infoMixMode, checkResetAll);
    		initParameterSet(smearCombo, "enumSmearing", EnumSmearing.values(), true, checkSmear, infoSmearing, checkResetAll);//true means not QE default
    		initParameterSet(occupCombo, "enumOccupation", EnumOccupations.values(), true, checkOccup, infoOccup, checkResetAll);//true means not QE default
			occupCombo.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			if (newValue.equals(EnumOccupations.smearing)) {
					smearCombo.setDisable(false);checkSmear.setDisable(false);
					gaussField.setDisable(false);//checkGauss.setDisable(false);
				}
				else {
					smearCombo.setDisable(true);checkSmear.setDisable(true);
					gaussField.setDisable(true);//checkGauss.setDisable(true);
				}
			});
			
			setComboListener(ecutwfcUnit, EnumUnitEnergy.values(), "enumEnergyUnit");//ecutwfc
			
			initIntegerParameterSet(maxStepField, "nElecMaxStep", EnumNumCondition.positive, "", checkMaxStep, infoMaxstep, checkResetAll);
			initDoubleParameterSet(mixingField, "mixBeta", EnumNumCondition.positive, "", checkMixBeta, infoMixBeta, checkResetAll);
			setDoubleFieldListener(ecutrhoField, "ecutRho",EnumNumCondition.positive);
			
			initDoubleParameterSet(convField, "elecConv", EnumNumCondition.positive, "", checkConv, infoConv, checkResetAll);
			checkConv.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{
				if (newValue) {ecutwfcUnit.getSelectionModel().select(EnumUnitEnergy.Ry);ecutwfcUnit.setDisable(true);}
				else {checkEcutwfcAvailable();}
			});
			convUnit.textProperty().bind(ecutwfcUnit.valueProperty().asString());
			
			checkK.setDisable(true);
			setIntegerFieldListener(kxField, "nkx",EnumNumCondition.positive);
			setIntegerFieldListener(kyField, "nky",EnumNumCondition.positive);
			setIntegerFieldListener(kzField, "nkz",EnumNumCondition.positive);
			
			checkGauss.setDisable(true);
			setDoubleFieldListener(gaussField, "degauss",EnumNumCondition.nonNegative);
			gaussUnit.textProperty().bind(ecutwfcUnit.valueProperty().asString());
			
			//checkResetAll
			checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			if(newValue!=null && !newValue.equals(allDefault)) {
    				checkRestart.setSelected(newValue);checkForce.setSelected(newValue);
    				checkStress.setSelected(newValue);checkEcutrho.setSelected(newValue);
    				checkMaxStep.setSelected(newValue);checkConv.setSelected(newValue);
    				checkMixMode.setSelected(newValue);checkMixBeta.setSelected(newValue);
    				checkOccup.setSelected(newValue);checkSmear.setSelected(newValue);
    				allDefault = newValue;
    			}
			});
    	}
    }
    private void checkEcutwfcAvailable() {
    	if (checkConv.isSelected()) return;// || checkGauss.isSelected()
    	else {ecutwfcUnit.setDisable(false);}
    }
    public void loadProjectParameters() {
    	super.loadProjectParameters();

    	InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
		if (iScf!=null) {
			setCombo(ecutwfcUnit, iScf.enumEnergyUnit);
			setField(ecutwfcField, iScf.ecutWfc);
			setField(ecutrhoField, iScf.ecutRho);
			setField(kxField, iScf.nkx);
			setField(kyField, iScf.nky);
			setField(kzField, iScf.nkz);
			setField(gaussField, iScf.degauss);
			
			checkEcutrho.setSelected(!iScf.ecutRho.isEnabled());
		}
    }

}
