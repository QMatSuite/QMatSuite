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
import com.consts.Constants.EnumStep;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.AnchorPane;
import main.MainClass;

public class InputTddftController extends InputController{

    @FXML
    private CheckBox checkDefaultAll;

    @FXML
    private Button infoDefaultAll;

    @FXML
    private TextField textMaxIterations;

    @FXML
    private CheckBox checkMaxIterations;

    @FXML
    private Button infoMaxIterations;

    @FXML
    private ComboBox<?> comboPolarizability;

    @FXML
    private CheckBox checkPolarizability;

    @FXML
    private Button infoPolarizability;

    @FXML
    private CheckBox checkLabelterations;

    @FXML
    private Button infoLabelterations;

    @FXML
    private CheckBox checkAllIterations;

    @FXML
    private Button infoAllIterations;

    @FXML
    private Label labelterations;

    @FXML
    private TextField textAllIterations;

    @FXML
    private ComboBox<?> comboExtrapolation;

    @FXML
    private CheckBox checkExtrapolation;

    @FXML
    private Button infoExtrapolation;

    @FXML
    private CheckBox checkDegauss;

    @FXML
    private Button infoDegauss;

    @FXML
    private TextField textDegauss;

    @FXML
    private Label labelDegauss;

    @FXML
    private ComboBox<?> comboEnergyUnit;

    @FXML
    private CheckBox checkEnergyUnit;

    @FXML
    private Button infoEnergyUnit;

    @FXML
    private TextField textEEnd;

    @FXML
    private Label labelEEnd;

    @FXML
    private CheckBox checkEEnd;

    @FXML
    private Button infoEEnd;

    @FXML
    private CheckBox checkEStart;

    @FXML
    private Button infoEStart;

    @FXML
    private TextField textEStart;

    @FXML
    private Label labelEStart;

    @FXML
    private TextField textEStep;

    @FXML
    private Label labelEStep;

    @FXML
    private CheckBox checkEStep;

    @FXML
    private Button infoEStep;

    @FXML
    private Label labelPolarizability;

    @FXML
    private CheckBox checkLabelPolarizability;

    @FXML
    private Button infoLabelPolarizability;

    @FXML
    private ToggleButton toggleEELS;

    @FXML
    private CheckBox checkEELS;

    @FXML
    private Button infoEELS;

    @FXML
    private Label statusInfo;

	@FXML private AnchorPane projectPane;

	public InputTddftController(MainClass mc) {
		super(mc, EnumStep.TDDFT);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		// TODO Auto-generated method stub
		
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();

	}

}
	






