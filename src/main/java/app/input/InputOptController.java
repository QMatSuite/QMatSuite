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

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.GridPane;
import main.MainClass;
import agent.InputAgentOpt;
import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellOptMethod;
import com.consts.Constants.EnumIonOptMethod;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitEnergy;

public class InputOptController extends InputController implements Initializable {

    @FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private Label restartLabel;

    @FXML
    private Label maxstepLabel;

    @FXML
    private Label vcLabel;

    @FXML
    private ToggleButton relaxCellToggle;

    @FXML
    private ToggleButton scfMustToggle;

    @FXML
    private Button infoRelaxCell;

    @FXML
    private Button infoMaxStep;

    @FXML
    private Button infoScfMust;

    @FXML
    private CheckBox checkRelaxCell;

    @FXML
    private CheckBox checkMaxStep;

    @FXML
    private CheckBox checkScfMust;

    @FXML
    private TextField textMaxStep;

    @FXML
    private Label ionConvLabel;

    @FXML
    private Label ionMethodLabel;

    @FXML
    private TextField eConvText;

    @FXML
    private ComboBox<EnumUnitEnergy> eConvUnit;

    @FXML
    private ComboBox<EnumIonOptMethod> ionRelaxCombo;

    @FXML
    private Button infoEConv;

    @FXML
    private Button infoIonMethod;

    @FXML
    private CheckBox checkEConv;

    @FXML
    private CheckBox checkIonMethod;

    @FXML
    private Label ionConvLabel1;

    @FXML
    private TextField fConvText;

    @FXML
    private CheckBox checkFConv;

    @FXML
    private Button infoFConv;

    @FXML
    private GridPane gridPaneCell;

    @FXML
    private Label cellConvLabel;

    @FXML
    private Label cellMethodLabel;

    @FXML
    private Label pressLabel;

    @FXML
    private Label cellFreeLabel;

    @FXML
    private TextField pConvText;

    @FXML
    private ComboBox<EnumCellOptMethod> cellRelaxCombo;

    @FXML
    private TextField pTargetText;

    @FXML
    private ComboBox<EnumCellDoFree> cellDoFreeCombo;

    @FXML
    private Button infoPConv;

    @FXML
    private Button infoCellMethod;

    @FXML
    private Button infoTargetP;

    @FXML
    private Button infoCellFree;

    @FXML
    private CheckBox checkPConv;

    @FXML
    private CheckBox checkCellMethod;

    @FXML
    private CheckBox checkTargetP;

    @FXML
    private CheckBox checkCellFree;
    
    @FXML
    private Label statusInfo;
    
    public InputOptController(MainClass mc) {
		super(mc);
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
		//connect fields in GUI to inputAgent
		
		relaxCellToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentOpt iOpt = (InputAgentOpt) mainClass.projectManager.getStepAgent(EnumStep.OPT);
			if (newValue) 
			{ 
				relaxCellToggle.setText("relax cell also");
				gridPaneCell.setVisible(true);
				if (iOpt!=null)  iOpt.boolRelaxCell.setValue(true);
			}
			else 
			{ 
				relaxCellToggle.setText("only ions"); 
				gridPaneCell.setVisible(false);
				if (iOpt!=null)  iOpt.boolRelaxCell.setValue(false);
			}
		});
		//initialize without cell
		relaxCellToggle.setSelected(false);relaxCellToggle.setText("only ions"); 
		gridPaneCell.setVisible(false);
		
		setIntegerFieldListener(textMaxStep, "nMaxSteps",EnumNumCondition.positive,EnumStep.OPT);
		setToggleListener(scfMustToggle, "boolScfMustConverge", EnumStep.OPT, "true", "false");
		setDoubleFieldListener(eConvText, "numEConv",EnumNumCondition.positive,EnumStep.OPT);
		setDoubleFieldListener(fConvText, "numFConv",EnumNumCondition.positive,EnumStep.OPT);
		setDoubleFieldListener(pConvText, "numPConv",EnumNumCondition.positive,EnumStep.OPT);
		setDoubleFieldListener(pTargetText, "numPTarget",EnumNumCondition.no,EnumStep.OPT);
		setComboListener(eConvUnit, EnumUnitEnergy.values(), "enumEUnit", EnumStep.OPT);//energy unit
		setComboListener(ionRelaxCombo, EnumIonOptMethod.values(), "enumOptMethodIon", EnumStep.OPT);
		setComboListener(cellRelaxCombo, EnumCellOptMethod.values(), "enumOptMethodCell", EnumStep.OPT);
		setComboListener(cellDoFreeCombo, EnumCellDoFree.values(), "enumCellDoFree", EnumStep.OPT);
		
		//reset checkBoxes
		resetToggleListener(checkRelaxCell, relaxCellToggle, "boolRelaxCell", EnumStep.OPT, checkResetAll);
		resetTextFieldIntegerListener(checkMaxStep, textMaxStep, "nMaxSteps", EnumStep.OPT, checkResetAll);
		resetToggleListener(checkScfMust, scfMustToggle, "boolScfMustConverge", EnumStep.OPT, checkResetAll);
		checkEConv.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentOpt iOpt = (InputAgentOpt) mainClass.projectManager.getStepAgent(EnumStep.OPT);
			if (iOpt==null || newValue==null) return;
			if (newValue) {eConvText.setText(Double.toString(iOpt.numEConv.resetDefault()));eConvText.setDisable(true);
			eConvUnit.getSelectionModel().select(EnumUnitEnergy.Ry);eConvUnit.setDisable(true);iOpt.numEConv.setEnabled(false);}
			else {eConvText.setDisable(false);iOpt.numEConv.setEnabled(true);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
		});
		resetTextFieldDoubleListener(checkFConv, fConvText, "numFConv", EnumStep.OPT, checkResetAll);
		resetComboBoxListener(checkIonMethod, ionRelaxCombo, "enumOptMethodIon", EnumStep.OPT, checkResetAll);
		resetTextFieldDoubleListener(checkPConv, pConvText, "numPConv", EnumStep.OPT, checkResetAll);
		resetComboBoxListener(checkCellMethod, cellRelaxCombo, "enumOptMethodCell", EnumStep.OPT, checkResetAll);
		resetTextFieldDoubleListener(checkTargetP, pTargetText, "numPTarget", EnumStep.OPT, checkResetAll);
		resetComboBoxListener(checkCellFree, cellDoFreeCombo, "enumCellDoFree", EnumStep.OPT, checkResetAll);

		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				checkRelaxCell.setSelected(newValue);checkMaxStep.setSelected(newValue);
				checkScfMust.setSelected(newValue);checkEConv.setSelected(newValue);
				checkFConv.setSelected(newValue);checkIonMethod.setSelected(newValue);
				checkPConv.setSelected(newValue);checkCellMethod.setSelected(newValue);
				checkTargetP.setSelected(newValue);checkCellFree.setSelected(newValue);
				allDefault = newValue;
			}
		});
	}
	public void loadProjectParameters() {
    	if (!ionRelaxCombo.getItems().isEmpty()) {
    		InputAgentOpt iOpt = (InputAgentOpt) mainClass.projectManager.getStepAgent(EnumStep.OPT);
    		if (iOpt!=null) {
    			
    			setToggle(relaxCellToggle, iOpt.boolRelaxCell);
    			setField(textMaxStep, iOpt.nMaxSteps);
    			setToggle(scfMustToggle, iOpt.boolScfMustConverge);
    			setField(eConvText, iOpt.numEConv);
    			setField(fConvText, iOpt.numFConv);
    			setField(pConvText, iOpt.numPConv);
    			setField(pTargetText, iOpt.numPTarget);
    			setCombo(eConvUnit, iOpt.enumEUnit);
    			setCombo(ionRelaxCombo, iOpt.enumOptMethodIon);
    			setCombo(cellRelaxCombo, iOpt.enumOptMethodCell);
    			setCombo(cellDoFreeCombo, iOpt.enumCellDoFree);
    			
    			
    			//load default checkBoxes
    			checkRelaxCell.setSelected(!iOpt.boolRelaxCell.isEnabled());
    			checkMaxStep.setSelected(!iOpt.nMaxSteps.isEnabled());
    			checkScfMust.setSelected(!iOpt.boolScfMustConverge.isEnabled());
    			checkEConv.setSelected(!iOpt.numEConv.isEnabled());
    			checkFConv.setSelected(!iOpt.numFConv.isEnabled());
    			checkIonMethod.setSelected(!iOpt.enumOptMethodIon.isEnabled());
    			checkPConv.setSelected(!iOpt.numPConv.isEnabled());
    			checkCellMethod.setSelected(!iOpt.enumOptMethodCell.isEnabled());
    			checkTargetP.setSelected(!iOpt.numPTarget.isEnabled());
    			checkCellFree.setSelected(!iOpt.enumCellDoFree.isEnabled());
    			
    		}
    	}
    }
}
