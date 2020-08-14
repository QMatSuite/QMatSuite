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

import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellOptMethod;
import com.consts.Constants.EnumIonOptMethod;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitEnergy;

import core.app.input.InputController;
import core.main.MainClass;

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
		super(mc, EnumStep.OPT);
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		//point all status messages to the Label statusInfo
		setPointerStatusTextField(statusInfo);
		//new
		initParameterSet(relaxCellToggle, "boolRelaxCell", "relax cell also", "only ions", checkRelaxCell, infoRelaxCell, checkResetAll);
		relaxCellToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			relaxCellSet(newValue);
		});
		//initialize without cell
		relaxCellSet(false);
		
		initParameterSet(scfMustToggle, "boolScfMustConverge", "true", "false", checkScfMust, infoScfMust, checkResetAll);
		
		initParameterSet(eConvUnit, "enumEUnit", EnumUnitEnergy.values(), checkEConv, infoEConv, checkResetAll);
		initParameterSet(ionRelaxCombo, "enumOptMethodIon", EnumIonOptMethod.values(), checkIonMethod, infoIonMethod, checkResetAll);
		initParameterSet(cellRelaxCombo, "enumOptMethodCell", EnumCellOptMethod.values(), checkCellMethod, infoCellMethod, checkResetAll);	
		initParameterSet(cellDoFreeCombo, "enumCellDoFree", EnumCellDoFree.values(), checkCellFree, infoCellFree, checkResetAll);
		
		initIntegerParameterSet(textMaxStep, "nMaxSteps", EnumNumCondition.positive, "", checkMaxStep, infoMaxStep, checkResetAll);
		initDoubleParameterSet(fConvText, "numFConv", EnumNumCondition.positive, "", checkFConv, infoFConv, checkResetAll);
		initDoubleParameterSet(pConvText, "numPConv", EnumNumCondition.positive, "", checkPConv, infoPConv, checkResetAll);
		initDoubleParameterSet(pTargetText, "numPTarget", EnumNumCondition.no, "", checkTargetP, infoTargetP, checkResetAll);
		initDoubleParameterSet(eConvText, "numEConv", EnumNumCondition.positive, "", checkEConv, infoEConv, checkResetAll);

		//reset checkBoxes
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
	private void relaxCellSet(boolean newValue) {
		if (newValue) 
		{ 
			relaxCellToggle.setText("relax cell also");
			gridPaneCell.setVisible(true);
		}
		else 
		{ 
			relaxCellToggle.setText("only ions"); 
			gridPaneCell.setVisible(false);
		}
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();
    }
}
