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
package app.centerwindow;

import java.net.URL;
import java.util.ResourceBundle;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;

public class Animate3DController implements Initializable{
	
	@FXML
    private Button buttonPrevious;

    @FXML
    private TextField textFieldStep;

    @FXML
    private Label labelTotalStep;

    @FXML
    private Button buttonNext;

    @FXML
    private Button buttonAutoPlay;

    @FXML
    private Label labelStatus;
    
	private WorkScene3D ws3d;
	
	public Animate3DController(WorkScene3D ws3dtmp) {
		ws3d = ws3dtmp;
	}
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setStatus("");
	}
	public void setStatus(String st) {
		labelStatus.setText(st);
	}
}
