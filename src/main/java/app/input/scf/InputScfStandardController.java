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
package main.java.app.input.scf;

import java.net.URL;
import java.util.ResourceBundle;

import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import main.java.MainClass;
import main.java.agent.InputAgentScf;
import main.java.app.input.InputController;
import main.java.com.consts.Constants.EnumMixingMode;
import main.java.com.consts.Constants.EnumNumCondition;
import main.java.com.consts.Constants.EnumOccupations;
import main.java.com.consts.Constants.EnumSmearing;
import main.java.com.consts.Constants.EnumStep;
import main.java.com.consts.Constants.EnumUnitEnergy;

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
		super(mc);
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		initialize();
    }
    public void initialize(){
    	if (occupCombo.getItems().isEmpty()) {
    		setToggleListener(restartToggle, "boolRestart", EnumStep.SCF, "restart", "from scratch");//restart mode
    		setToggleListener(forceToggle, "boolForce", EnumStep.SCF, "on", "off");//force
    		setToggleListener(stressToggle, "boolStress", EnumStep.SCF, "on", "off");//stress
    		
    		setComboListener(ecutwfcUnit, EnumUnitEnergy.values(), "enumEnergyUnit", EnumStep.SCF);//ecutwfc
    		//setDoubleFieldListener(ecutwfcField, "ecutWfc",EnumNumCondition.positive);
    		ecutwfcField.textProperty().addListener((observable, oldValue, newValue) -> {
    			InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
    			if (ia==null) return;
    			Double tmp = str2double(newValue);
				if (tmp!=null) {
					if(tmp<=0) {statusInfo.setText("Must be positive!");return;}
				
    				statusInfo.setText("");
    				ia.ecutWfc.setValue(tmp);
    				if (checkEcutrho.isSelected()) {
    					ecutrhoField.setText(String.valueOf(tmp*4.0));
    				}
				}
    		});
    		setDoubleFieldListener(ecutrhoField, "ecutRho",EnumNumCondition.positive,EnumStep.SCF);
    		convUnit.textProperty().bind(ecutwfcUnit.valueProperty().asString());
    		
    		setIntegerFieldListener(maxStepField, "nElecMaxStep",EnumNumCondition.positive,EnumStep.SCF);
    		setDoubleFieldListener(convField, "elecConv",EnumNumCondition.positive,EnumStep.SCF);
    		
    		
    		setComboListener(mixingModeCombo, EnumMixingMode.values(), "enumMixing", EnumStep.SCF);//mixing mode
			
			setDoubleFieldListener(mixingField, "mixBeta",EnumNumCondition.positive,EnumStep.SCF);
			setIntegerFieldListener(kxField, "nkx",EnumNumCondition.positive,EnumStep.SCF);
			setIntegerFieldListener(kyField, "nky",EnumNumCondition.positive,EnumStep.SCF);
			setIntegerFieldListener(kzField, "nkz",EnumNumCondition.positive,EnumStep.SCF);
			
    		gaussUnit.textProperty().bind(ecutwfcUnit.valueProperty().asString());
    		
    		//occupation list
			ObservableList<EnumOccupations> occup = 
	    		    FXCollections.observableArrayList(EnumOccupations.values());
			occupCombo.setItems(occup);
			occupCombo.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
    		{ 
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf!=null && newValue!=null) {
					iScf.enumOccupation.setValue(newValue);
					if (newValue.equals(EnumOccupations.smearing)) {
						smearCombo.setDisable(false);checkSmear.setDisable(false);
						gaussField.setDisable(false);//checkGauss.setDisable(false);
					}
					else {
						smearCombo.setDisable(true);checkSmear.setDisable(true);
						gaussField.setDisable(true);checkGauss.setDisable(true);
					}
				}
			});
			
			setComboListener(smearCombo, EnumSmearing.values(), "enumSmearing", EnumStep.SCF);//smearing list
			
			setDoubleFieldListener(gaussField, "degauss",EnumNumCondition.nonNegative,EnumStep.SCF);
			
			//reset 
			resetToggleListener(checkRestart, restartToggle, "boolRestart", EnumStep.SCF, checkResetAll);
			resetToggleListener(checkForce, forceToggle, "boolForce", EnumStep.SCF, checkResetAll);
			resetToggleListener(checkStress, stressToggle, "boolStress", EnumStep.SCF, checkResetAll);
			checkEcutwfc.setDisable(true);
			
			
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
			resetTextFieldIntegerListener(checkMaxStep, maxStepField, "nElecMaxStep", EnumStep.SCF, checkResetAll);
			checkConv.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf==null || newValue==null) return;
				if (newValue) {convField.setText(Double.toString(iScf.elecConv.resetDefault()));convField.setDisable(true);
				ecutwfcUnit.getSelectionModel().select(EnumUnitEnergy.Ry);ecutwfcUnit.setDisable(true);iScf.elecConv.setEnabled(false);}
				else {convField.setDisable(false);checkEcutwfcAvailable();iScf.elecConv.setEnabled(true);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
			});
			resetComboBoxListener(checkMixMode, mixingModeCombo, "enumMixing", EnumStep.SCF, checkResetAll);
			resetTextFieldDoubleListener(checkMixBeta, mixingField, "mixBeta", EnumStep.SCF, checkResetAll);
			checkK.setDisable(true);
			resetComboBoxListener(checkOccup, occupCombo, "enumOccupation", EnumStep.SCF, checkResetAll, true);//true means not QE default
			resetComboBoxListener(checkSmear, smearCombo, "enumSmearing", EnumStep.SCF, checkResetAll, true);//true means not QE default
			checkGauss.setDisable(true);
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
			//context help
			setInfoButton(infoRestart,"infoRestart");
			setInfoButton(infoForce,"infoForce");
    	}
    }
    private void checkEcutwfcAvailable() {
    	if (checkConv.isSelected()) return;// || checkGauss.isSelected()
    	else {ecutwfcUnit.setDisable(false);}
    }
    
    public void loadProjectParameters() {
    	if (!occupCombo.getItems().isEmpty()) {
    		InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
    		if (iScf!=null) {
    			setCombo(occupCombo, iScf.enumOccupation);
    			setToggle(restartToggle, iScf.boolRestart);
    			setToggle(forceToggle, iScf.boolForce);
    			setToggle(stressToggle, iScf.boolStress);
    			setCombo(ecutwfcUnit, iScf.enumEnergyUnit);
    			setCombo(mixingModeCombo, iScf.enumMixing);
    			setCombo(smearCombo, iScf.enumSmearing);
    			//occupCombo.setValue((EnumOccupations)iScf.enumOccupation.getValue());
    			//restartToggle.setSelected(iScf.boolRestart.getValue());
    			//forceToggle.setSelected(iScf.boolForce.getValue());
    			//stressToggle.setSelected(iScf.boolStress.getValue());
    			//ecutwfcUnit.setValue((EnumUnitEnergy)iScf.enumEnergyUnit.getValue());
    			setField(ecutwfcField, iScf.ecutWfc);
    			setField(ecutrhoField, iScf.ecutRho);
        		setField(maxStepField, iScf.nElecMaxStep);
    			setField(convField, iScf.elecConv);
    			//mixingModeCombo.setValue((EnumMixingMode)iScf.enumMixing.getValue());
    			setField(mixingField, iScf.mixBeta);
    			setField(kxField, iScf.nkx);
    			setField(kyField, iScf.nky);
    			setField(kzField, iScf.nkz);
    			//smearCombo.setValue((EnumSmearing) iScf.enumSmearing.getValue());
    			setField(gaussField, iScf.degauss);
    			
    			//load default checkBoxes
    			checkRestart.setSelected(!iScf.boolRestart.isEnabled());
    			checkForce.setSelected(!iScf.boolForce.isEnabled());
    			checkStress.setSelected(!iScf.boolStress.isEnabled());
    			checkEcutwfc.setSelected(!iScf.ecutWfc.isEnabled());
    			checkEcutrho.setSelected(!iScf.ecutRho.isEnabled());
    			checkMaxStep.setSelected(!iScf.nElecMaxStep.isEnabled());
    			checkConv.setSelected(!iScf.elecConv.isEnabled());
    			checkMixMode.setSelected(!iScf.enumMixing.isEnabled());
    			checkMixBeta.setSelected(!iScf.mixBeta.isEnabled());
    			checkK.setSelected(!iScf.nkx.isEnabled());
    			checkOccup.setSelected(!iScf.enumOccupation.isEnabled());
    			checkSmear.setSelected(!iScf.enumSmearing.isEnabled());
    			checkGauss.setSelected(!iScf.degauss.isEnabled());
    			
    		}
    	}
    }

}
