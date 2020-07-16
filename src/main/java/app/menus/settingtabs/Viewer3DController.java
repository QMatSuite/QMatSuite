/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.menus.settingtabs;


import java.net.URL;
import java.util.ResourceBundle;

import com.error.ShowAlert;

import app.centerwindow.WorkScene3D;
import javafx.beans.binding.Bindings;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.geometry.Insets;
import javafx.scene.control.TextField;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListCell;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.CornerRadii;
import javafx.scene.layout.StackPane;
import javafx.scene.paint.Color;
import main.MainClass;

public class Viewer3DController implements Initializable{

	@FXML
    private AnchorPane acp;

    @FXML
    private TextField textBondThick;

    @FXML
    private TextField textAtomSize;

    @FXML
    private TextField textMaxNCells;

    @FXML
    private Label labelBondThick,
    labelAtomSize,
    labelMaxNCells,
    labelBackgroundColor;
    
    @FXML
    private ComboBox<Color> comboBackgroundColor;
	    
    private MainClass mainClass;
    
    public Viewer3DController(MainClass mc) {
    	mainClass = mc;
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		comboBackgroundColor.getItems().addAll(Color.SILVER,Color.WHITE,Color.LIGHTGRAY,Color.GRAY,Color.DARKGREY,Color.BLACK);
		comboBackgroundColor.buttonCellProperty().bind(Bindings.createObjectBinding(() -> {
		    final Color finalColor = comboBackgroundColor.getSelectionModel().getSelectedItem();
		    
		    // Get the arrow button of the combobox
		    StackPane arrowButton = (StackPane) comboBackgroundColor.lookup(".arrow-button");
		    
		    return new ListCell<Color>() {

		        @Override
		        protected void updateItem(Color item, boolean empty) {
		            super.updateItem(item, empty);

		            if (empty || item == null) {
		                setBackground(Background.EMPTY);
		                setText("");
		            } else {
		                setBackground(new Background(new BackgroundFill(finalColor, CornerRadii.EMPTY, Insets.EMPTY)));
		                setText(item.toString());
		            }
		            
		            // Set the background of the arrow
		            if (arrowButton != null) {arrowButton.setBackground(getBackground());}
		        }

		    };
		}, comboBackgroundColor.valueProperty()));
		comboBackgroundColor.setCellFactory(lv -> new ListCell<Color>(){
		    @Override
		    protected void updateItem(Color item, boolean empty) {
		        super.updateItem(item, empty);

		        if (empty || item == null) {
		            setBackground(Background.EMPTY);
		            setText("");
		        } else {
		            setBackground(new Background(new BackgroundFill(item,CornerRadii.EMPTY,Insets.EMPTY)));
		            setText(item.toString());
		        }
		    }

		});
		loadValues();
	}
	public void loadValues() {
		labelBondThick.setText(Integer.toString(WorkScene3D.getBondThick()));
		labelAtomSize.setText(Double.toString(WorkScene3D.getBallRadiusAtom()));
		labelMaxNCells.setText(Integer.toString(WorkScene3D.getMaxTrialCells()));
		labelBackgroundColor.setText(WorkScene3D.getBackgroundColor().toString());
		labelBackgroundColor.setBackground(new Background(new BackgroundFill(WorkScene3D.getBackgroundColor(),CornerRadii.EMPTY,Insets.EMPTY)));
		
		textBondThick.setText(labelBondThick.getText());
		textAtomSize.setText(labelAtomSize.getText());
		textMaxNCells.setText(labelMaxNCells.getText());
		comboBackgroundColor.getSelectionModel().select(WorkScene3D.getBackgroundColor());
	}
	public void saveChanges() {
		String msg="";
		try {
			msg+=WorkScene3D.setBondThick(Integer.valueOf(textBondThick.getText()));//not null
		}
		catch(Exception e) {msg+="Bond thickness must be integer.\n";}
		try {
			msg+=WorkScene3D.setBallRadiusAtom(Double.valueOf(textAtomSize.getText()));
		}
		catch(Exception e) {msg+="Ball radius must be double.\n";}
		try {
			msg+=WorkScene3D.setMaxTrialCells(Integer.valueOf(textMaxNCells.getText()));
		}
		catch(Exception e) {msg+="Max number of trial cells must be integer.\n";}
		if(comboBackgroundColor.getSelectionModel().getSelectedItem()!=null) {
			WorkScene3D.setBackgroundColor(comboBackgroundColor.getSelectionModel().getSelectedItem());
		}
		else {
			msg+="Null selection of background color.\n";
		}
		if(!msg.isEmpty()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", msg);
		}
		loadValues();
	}
}