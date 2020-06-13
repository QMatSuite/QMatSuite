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

import main.MainClass;
import agent.InputAgentMd;
import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellMdMethod;
import com.consts.Constants.EnumInProgram;
import com.consts.Constants.EnumIonMdMethod;
import com.consts.Constants.EnumIonVcmdMethod;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumThermalstat;
import com.consts.Constants.EnumUnitTime;
import javafx.collections.FXCollections;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.GridPane;

public class InputMdController extends InputController {
	
    @FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private Label mdstepLabel;

    @FXML
    private Label timestepLabel;

    @FXML
    private TextField mdStepField;

    @FXML
    private TextField timestepField;

    @FXML
    private ComboBox<EnumUnitTime> timestepUnit;

    @FXML
    private Button infoMdStep;

    @FXML
    private Button infoTimeStep;

    @FXML
    private Button infoIonDynamics;

    @FXML
    private ComboBox<EnumInProgram> comboIonDynamics;

    @FXML
    private Label vcLabel;

    @FXML
    private ToggleButton toggleCellMove;

    @FXML
    private Button infoCellMove;

    @FXML
    private CheckBox checkMdStep;

    @FXML
    private CheckBox checkTimeStep;

    @FXML
    private CheckBox checkIonDynamics;

    @FXML
    private CheckBox checkCellMove;

    @FXML
    private Label ctrlTempLabel;

    @FXML
    private ComboBox<EnumThermalstat> comboThermalstat;

    @FXML
    private Button infoThermalstat;

    @FXML
    private Label tempLabel;

    @FXML
    private TextField tempField;

    @FXML
    private Button infoTargetT;

    @FXML
    private CheckBox checkThermalstat;

    @FXML
    private CheckBox checkTargetT;

    @FXML
    private GridPane gridThermAdvanced;

    @FXML
    private TextField tolpField;

    @FXML
    private TextField nraiseField;

    @FXML
    private TextField deltatField;

    @FXML
    private Button infoThermAdvanced;

    @FXML
    private CheckBox checkThermAdvanced;

    @FXML
    private GridPane gridCellDynamics;

    @FXML
    private Label cellMethodLabel;

    @FXML
    private Label pressLabel;

    @FXML
    private Label cellFreeLabel;

    @FXML
    private ComboBox<EnumCellMdMethod> comboCellMove;

    @FXML
    private TextField pressField;

    @FXML
    private ComboBox<EnumCellDoFree> comboCellDoFree;

    @FXML
    private Button infoCellDynamics;

    @FXML
    private Button infoP;

    @FXML
    private Button infoCellDoFree;

    @FXML
    private CheckBox checkCellDynamics;

    @FXML
    private CheckBox checkP;

    @FXML
    private CheckBox checkCellDoFree;
    
    @FXML
    private Label statusInfo;
    
    public InputMdController(MainClass mc) {
		super(mc);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
		
		//connect fields in GUI to inputAgent
		setIntegerFieldListener(mdStepField, "mdSteps",EnumNumCondition.positive,EnumStep.BOMD);
		setDoubleFieldListener(timestepField, "timeStep",EnumNumCondition.positive,EnumStep.BOMD);
		setComboListener(timestepUnit, EnumUnitTime.values(), "enumTimeUnit", EnumStep.BOMD);
		
		toggleCellMove.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentMd iMd = (InputAgentMd) mainClass.projectManager.getStepAgent(EnumStep.BOMD);
			if (newValue) 
			{ 
				toggleCellMove.setText("move cell also");
				gridCellDynamics.setVisible(true);
				comboIonDynamics.setItems(FXCollections.observableArrayList(EnumIonVcmdMethod.values()));
				comboIonDynamics.getSelectionModel().select(EnumIonVcmdMethod.beeman);
				if (iMd!=null)  {iMd.boolMoveCell.setValue(true);}
			}
			else 
			{ 
				toggleCellMove.setText("only ions"); 
				gridCellDynamics.setVisible(false);
				comboIonDynamics.setItems(FXCollections.observableArrayList(EnumIonMdMethod.values()));
				//iMd.enumMdMethodIon.setValue(EnumIonMdMethod.verlet);
				comboIonDynamics.getSelectionModel().select(EnumIonMdMethod.verlet);
				if (iMd!=null)  {iMd.boolMoveCell.setValue(false);}
			}
		});
		//initialize without cell
		toggleCellMove.setSelected(false);toggleCellMove.setText("only ions"); 
		gridCellDynamics.setVisible(false);
		comboIonDynamics.setItems(FXCollections.observableArrayList(EnumIonMdMethod.values()));
		setComboListener(comboIonDynamics, EnumIonMdMethod.values(), "enumMdMethodIon", EnumStep.BOMD);
		
		setComboListener(comboThermalstat, EnumThermalstat.values(), "enumThermalstat", EnumStep.BOMD);
		setDoubleFieldListener(tempField, "temperature",EnumNumCondition.nonNegative,EnumStep.BOMD);
		setDoubleFieldListener(tolpField, "tolp",EnumNumCondition.nonNegative,EnumStep.BOMD);
		setIntegerFieldListener(nraiseField, "nraise",EnumNumCondition.positive,EnumStep.BOMD);
		setDoubleFieldListener(deltatField, "deltat",EnumNumCondition.no,EnumStep.BOMD);//can be negative
		
		setComboListener(comboCellMove, EnumCellMdMethod.values(), "enumMdMethodCell", EnumStep.BOMD);
		setDoubleFieldListener(pressField, "pressure",EnumNumCondition.no,EnumStep.BOMD);
		setComboListener(comboCellDoFree, EnumCellDoFree.values(), "enumCellDoFree", EnumStep.BOMD);
		
		//reset buttons
		resetTextFieldIntegerListener(checkMdStep, mdStepField, "mdSteps", EnumStep.BOMD, checkResetAll);
		checkTimeStep.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentMd iMd = (InputAgentMd) mainClass.projectManager.getStepAgent(EnumStep.BOMD);
			if (iMd==null || newValue==null) return;
			if (newValue) {timestepField.setText(Double.toString(iMd.timeStep.resetDefault()));timestepField.setDisable(true);
			timestepUnit.getSelectionModel().select(EnumUnitTime.Ry);timestepUnit.setDisable(true);iMd.timeStep.setEnabled(false);}
			else {timestepField.setDisable(false);timestepUnit.setDisable(false);iMd.timeStep.setEnabled(true);
			if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
		});
		resetToggleListener(checkCellMove, toggleCellMove, "boolMoveCell", EnumStep.BOMD, checkResetAll);
		checkIonDynamics.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentMd iMd = (InputAgentMd) mainClass.projectManager.getStepAgent(EnumStep.BOMD);
			if (iMd==null || newValue==null) return;
			
			if (newValue) {
				if(comboIonDynamics.getItems().contains(EnumIonMdMethod.verlet)) 
				{comboIonDynamics.getSelectionModel().select(EnumIonMdMethod.verlet);}
				else if(comboIonDynamics.getItems().contains(EnumIonVcmdMethod.beeman))
				{comboIonDynamics.getSelectionModel().select(EnumIonVcmdMethod.beeman);}
				else return;
				comboIonDynamics.setDisable(true);iMd.enumMdMethodIon.setEnabled(false);
			}
			else {
				comboIonDynamics.setDisable(false);iMd.enumMdMethodIon.setEnabled(true);
				if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}
			}
		});
		resetComboBoxListener(checkThermalstat, comboThermalstat, "enumThermalstat", EnumStep.BOMD, checkResetAll);
		resetTextFieldDoubleListener(checkTargetT, tempField, "temperature", EnumStep.BOMD, checkResetAll);
		//same checkbox, three fields
		resetTextFieldDoubleListener(checkThermAdvanced, tolpField, "tolp", EnumStep.BOMD, checkResetAll);
		resetTextFieldIntegerListener(checkThermAdvanced, nraiseField, "nraise", EnumStep.BOMD, checkResetAll);
		resetTextFieldDoubleListener(checkThermAdvanced, deltatField, "deltat", EnumStep.BOMD, checkResetAll);
		
		resetComboBoxListener(checkCellDynamics, comboCellMove, "enumMdMethodCell", EnumStep.BOMD, checkResetAll);
		resetTextFieldDoubleListener(checkP, pressField, "pressure", EnumStep.BOMD, checkResetAll);
		resetComboBoxListener(checkCellDoFree, comboCellDoFree, "enumCellDoFree", EnumStep.BOMD, checkResetAll);
		
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				checkMdStep.setSelected(newValue);checkTimeStep.setSelected(newValue);
				checkCellMove.setSelected(newValue);checkIonDynamics.setSelected(newValue);
				checkThermalstat.setSelected(newValue);checkTargetT.setSelected(newValue);
				checkThermAdvanced.setSelected(newValue);checkCellDynamics.setSelected(newValue);
				checkP.setSelected(newValue);checkCellDoFree.setSelected(newValue);
				allDefault = newValue;
			}
		});
	}
	public void loadProjectParameters() {
		if (!timestepUnit.getItems().isEmpty()) {
    		InputAgentMd iMd = (InputAgentMd) mainClass.projectManager.getStepAgent(EnumStep.BOMD);
    		if (iMd!=null) {
    			
    			setField(mdStepField, iMd.mdSteps);
    			setField(timestepField, iMd.timeStep);
    			setCombo(timestepUnit, iMd.enumTimeUnit);
    			setToggle(toggleCellMove, iMd.boolMoveCell);
    			setCombo(comboIonDynamics, iMd.enumMdMethodIon);
    			
    			setCombo(comboThermalstat, iMd.enumThermalstat);
    			setField(tempField, iMd.temperature);
    			setField(tolpField, iMd.tolp);
    			setField(nraiseField, iMd.nraise);
    			setField(deltatField, iMd.deltat);
    			
    			setCombo(comboCellMove, iMd.enumMdMethodCell);
    			setField(pressField, iMd.pressure);
    			setCombo(comboCellDoFree, iMd.enumCellDoFree);
    			
    			
    			//load default checkBoxes
    			checkMdStep.setSelected(!iMd.mdSteps.isEnabled());
    			checkTimeStep.setSelected(!iMd.timeStep.isEnabled());
				checkCellMove.setSelected(!iMd.boolMoveCell.isEnabled());
				checkIonDynamics.setSelected(!iMd.enumMdMethodIon.isEnabled());
				checkThermalstat.setSelected(!iMd.enumThermalstat.isEnabled());
				checkTargetT.setSelected(!iMd.temperature.isEnabled());
				checkThermAdvanced.setSelected(!iMd.tolp.isEnabled());
				checkCellDynamics.setSelected(!iMd.enumMdMethodCell.isEnabled());
				checkP.setSelected(!iMd.pressure.isEnabled());
				checkCellDoFree.setSelected(!iMd.enumCellDoFree.isEnabled());
    			
    		}
    	}
	}

}

