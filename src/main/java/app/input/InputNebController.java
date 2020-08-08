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
import java.util.ArrayList;
import java.util.ResourceBundle;

import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumOptSchemeNeb;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumStringMethod;

import agent.InputAgentGeo;
import agent.InputAgentNeb;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.GridPane;
import main.MainClass;

public class InputNebController extends InputController{
	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private ComboBox<String> comboGeoStart;

    @FXML
    private Button infoGeoStart;

    @FXML
    private ComboBox<String> comboGeoEnd;

    @FXML
    private Button infoGeoEnd;

    @FXML
    private ToggleButton toggleMinImage;

    @FXML
    private CheckBox checkMinImage;

    @FXML
    private Button infoMinImage;

    @FXML
    private GridPane panelAdvanced;

    @FXML
    private ToggleButton toggleRestart;

    @FXML
    private CheckBox checkRestart;

    @FXML
    private Button infoRestart;

    @FXML
    private TextField textNumImage;

    @FXML
    private Button infoNumImage;

    @FXML
    private TextField textMaxSteps;

    @FXML
    private Button infoMaxSteps;

    @FXML
    private ComboBox<EnumOptSchemeNeb> comboOptScheme;

    @FXML
    private CheckBox checkOptScheme;

    @FXML
    private Button infoOptScheme;

    @FXML
    private ToggleButton toggleCi;

    @FXML
    private CheckBox checkCi;

    @FXML
    private Button infoCi;

    @FXML
    private ToggleButton toggleFirstLastOpt;

    @FXML
    private CheckBox checkFirstLastOpt;

    @FXML
    private Button infoFirstLastOpt;

    @FXML
    private TextField textConv;

    @FXML
    private CheckBox checkConv;

    @FXML
    private Button infoConv;

    @FXML
    private TextField textStepLength;

    @FXML
    private CheckBox checkStepLength;

    @FXML
    private Button infoStepLength;

    @FXML
    private ComboBox<EnumStringMethod> comboMethod;

    @FXML
    private CheckBox checkMethod;

    @FXML
    private Button infoMethod;

    @FXML
    private Label statusInfo;

    
	public InputNebController(MainClass mc) {
		super(mc, EnumStep.NEB);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		comboGeoStart.getSelectionModel().selectedIndexProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null) {
				int intVal = newValue.intValue();
				ArrayList<InputAgentGeo> iGeoArr = mainClass.projectManager.getGeoList();
				if(iGeoArr!=null && intVal >=0 && intVal < iGeoArr.size()) {
					InputAgentNeb iNeb = (InputAgentNeb) mainClass.projectManager.getStepAgent(EnumStep.NEB);
					if (iNeb!=null) {
						iNeb.startGeo = intVal;
					}
				}
			}
		});
		
		comboGeoEnd.getSelectionModel().selectedIndexProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null) {
				int intVal = newValue.intValue();
				ArrayList<InputAgentGeo> iGeoArr = mainClass.projectManager.getGeoList();
				if(iGeoArr!=null && intVal >=0 && intVal < iGeoArr.size()) {
					InputAgentNeb iNeb = (InputAgentNeb) mainClass.projectManager.getStepAgent(EnumStep.NEB);
					if (iNeb!=null) {
						iNeb.endGeo = intVal;
					}
				}
			}
		});
		
		initParameterSet(toggleMinImage, "boolMinImage", "on", "off", checkMinImage, infoMinImage, checkResetAll);
		initParameterSet(comboMethod, "enumMethod", EnumStringMethod.values(), checkMethod, infoMethod, checkResetAll);
		initParameterSet(toggleRestart, "boolRestart", "restart", "from scratch", checkRestart, infoRestart, checkResetAll);

		//initIntegerParameterSet(textNumImage, "numOfImages", EnumNumCondition.gt3, "", null, infoNumImage, checkResetAll);
		//initIntegerParameterSet(textMaxSteps, "nstepPath", EnumNumCondition.positive, "", null, infoMaxSteps, checkResetAll);
		
		setIntegerFieldListener(textNumImage, "numOfImages",EnumNumCondition.gt3);
		setIntegerFieldListener(textMaxSteps, "nstepPath",EnumNumCondition.positive);
		
		initDoubleParameterSet(textConv, "pathThr", EnumNumCondition.positive, "", checkConv, infoConv, checkResetAll);
		initDoubleParameterSet(textStepLength, "ds", EnumNumCondition.positive, "", checkStepLength, infoStepLength, checkResetAll);
		initParameterSet(comboOptScheme, "enumOptScheme", EnumOptSchemeNeb.values(), checkOptScheme, infoOptScheme, checkResetAll);
		initParameterSet(toggleCi, "boolCI", "on", "off", checkCi, infoCi, checkResetAll);
		initParameterSet(toggleFirstLastOpt, "firstLastOpt", "on", "off", checkFirstLastOpt, infoFirstLastOpt, checkResetAll);
		
		//checkAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				checkMinImage.setSelected(newValue);
				checkMethod.setSelected(newValue);
				checkRestart.setSelected(newValue);
				checkConv.setSelected(newValue);
				checkStepLength.setSelected(newValue);
				checkOptScheme.setSelected(newValue);
				checkCi.setSelected(newValue);
				checkFirstLastOpt.setSelected(newValue);
			}
		});
	}
	
	public void loadProjectParameters() {
		super.loadProjectParameters();
		
		comboGeoStart.getItems().clear();
		comboGeoStart.getItems().addAll(mainClass.projectManager.getGeoName());
		
		comboGeoEnd.getItems().clear();
		comboGeoEnd.getItems().addAll(mainClass.projectManager.getGeoName());
		
		InputAgentNeb iNeb = (InputAgentNeb) mainClass.projectManager.getStepAgent(EnumStep.NEB);
		if (iNeb!=null) {
			comboGeoStart.getSelectionModel().select(iNeb.startGeo);
			comboGeoEnd.getSelectionModel().select(iNeb.endGeo);

			setField(textNumImage, iNeb.numOfImages);
			setField(textMaxSteps, iNeb.nstepPath);
		}
    }

}

