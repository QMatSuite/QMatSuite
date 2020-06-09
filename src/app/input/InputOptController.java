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
    private ComboBox<?> eConvUnit;

    @FXML
    private ComboBox<?> ionRelaxCombo;

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
    private ComboBox<?> cellRelaxCombo;

    @FXML
    private TextField pTargetText;

    @FXML
    private ComboBox<?> cellDoFreeCombo;

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
    

    
    public InputOptController(MainClass mc) {
		super(mc);
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		// TODO Auto-generated method stub
		
	}

}
