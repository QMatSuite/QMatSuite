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
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import main.MainClass;

public class InputBandsController extends InputController{
	
	@FXML
    private Label nbandLabel;

    @FXML
    private TextField textNBands;

    @FXML
    private Button infoNBands;

    @FXML
    private CheckBox checkNBands;

    @FXML
    private ComboBox<?> comboKPathUnit;

    @FXML
    private Button infoKPath;

    @FXML
    private Button buttonDelete;

    @FXML
    private Button buttonEdit;

    @FXML
    private Button buttonClearInput;

    @FXML
    private TextField textKx;

    @FXML
    private TextField textKy;

    @FXML
    private TextField textKz;

    @FXML
    private TextField textNk;

    @FXML
    private TextField textKLabel;

    @FXML
    private Button buttonAdd;

    @FXML
    private TableView<?> tableKPath;

    @FXML
    private TableColumn<?, ?> columnLabel;

    @FXML
    private TableColumn<?, ?> columnKx;

    @FXML
    private TableColumn<?, ?> columnKy;

    @FXML
    private TableColumn<?, ?> columnKz;

    @FXML
    private TableColumn<?, ?> columnNk;
	
	public InputBandsController (MainClass mc) {
		super(mc, EnumStep.BANDS);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		// TODO Auto-generated method stub
		
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();

	}
}
