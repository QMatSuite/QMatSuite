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

import agent.InputAgentMd;
import core.app.input.InputController;
import core.com.consts.ConstantsGeneral.EnumInProgram;
import core.main.MainClass;

import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellMdMethod;
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
import javafx.scene.layout.VBox;

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
    private Button infoCellDynamics,
    infoP,
    infoCellDoFree,
    infoNoSym;

    @FXML
    private CheckBox checkCellDynamics,
    checkP,
    checkCellDoFree,
    checkNoSym;
    
    @FXML
    private Label statusInfo;
    
    @FXML
    private VBox vboxOptionalThermalstat;
    
    @FXML
    private ToggleButton toggleNoSym;
    
    
    public InputMdController(MainClass mc) {
		super(mc, EnumStep.BOMD);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
		
		//new
		initParameterSet(timestepUnit, "enumTimeUnit", EnumUnitTime.values(), checkTimeStep, infoTimeStep, checkResetAll);
		initParameterSet(toggleCellMove, "boolMoveCell", "move cell also", "only ions", checkCellMove, infoIonDynamics, checkResetAll);
		toggleCellMove.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null) {toggleCellMoveCall(newValue);}
		});
		//initialize without cell
		toggleCellMoveCall(false);
		
		initParameterSet(toggleNoSym, "boolNoSym", "ON", "OFF", checkNoSym, infoNoSym, checkResetAll);
		setComboListener(comboIonDynamics, EnumIonMdMethod.values(), "enumMdMethodIon");
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
		
		initParameterSet(comboCellMove, "enumMdMethodCell", EnumCellMdMethod.values(), checkCellDynamics, infoCellDynamics, checkResetAll);
		
		initParameterSet(comboThermalstat, "enumThermalstat", EnumThermalstat.values(), checkThermalstat, infoThermalstat, checkResetAll);
		initParameterSet(comboCellDoFree, "enumCellDoFree", EnumCellDoFree.values(), checkCellDoFree, infoCellDoFree, checkResetAll);

		comboThermalstat.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
		{ 
			//second listener for comboThermalstat
			boolean hasTControl = !EnumThermalstat.non.equals(newValue);
			vboxOptionalThermalstat.setVisible(hasTControl);
			checkThermAdvanced.setVisible(hasTControl);
			checkTargetT.setVisible(hasTControl);
		});
		//initialize with all invisible because comboThermalstat is defaulted to non
		vboxOptionalThermalstat.setVisible(false);
		checkThermAdvanced.setVisible(false);checkTargetT.setVisible(false);
				
		initIntegerParameterSet(mdStepField, "mdSteps", EnumNumCondition.positive, "", checkMdStep, infoMdStep, checkResetAll);
		initDoubleParameterSet(timestepField, "timeStep", EnumNumCondition.positive, "", checkTimeStep, infoTimeStep, checkResetAll);
		initDoubleParameterSet(tempField, "temperature", EnumNumCondition.nonNegative, "", checkTargetT, infoTargetT, checkResetAll);
		initDoubleParameterSet(tolpField, "tolp", EnumNumCondition.nonNegative, "", checkThermAdvanced, infoThermAdvanced, checkResetAll);
		initIntegerParameterSet(nraiseField, "nraise", EnumNumCondition.positive, "", checkThermAdvanced, infoThermAdvanced, checkResetAll);
		initDoubleParameterSet(deltatField, "deltat", EnumNumCondition.no, "", checkThermAdvanced, infoThermAdvanced, checkResetAll);//can be negative
		initDoubleParameterSet(pressField, "pressure", EnumNumCondition.no, "", checkP, infoP, checkResetAll);
		
		//resetAll
		
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
	private void toggleCellMoveCall(boolean bl) {
		if (bl) 
		{ 
			gridCellDynamics.setVisible(true);
			comboIonDynamics.setItems(FXCollections.observableArrayList(EnumIonVcmdMethod.values()));
			comboIonDynamics.getSelectionModel().select(EnumIonVcmdMethod.beeman);

		}
		else 
		{
			gridCellDynamics.setVisible(false);
			comboIonDynamics.setItems(FXCollections.observableArrayList(EnumIonMdMethod.values()));
			comboIonDynamics.getSelectionModel().select(EnumIonMdMethod.verlet);
		}
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();

		InputAgentMd iMd = (InputAgentMd) mainClass.projectManager.getStepAgent(EnumStep.BOMD);
		if (iMd!=null) {
			setCombo(comboIonDynamics, iMd.enumMdMethodIon);
			checkIonDynamics.setSelected(!iMd.enumMdMethodIon.isEnabled());	
		}
	}

}

