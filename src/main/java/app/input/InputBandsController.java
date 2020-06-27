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

import com.consts.Constants.EnumKUnitBands;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;
import agent.InputAgentBands;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import javafx.scene.control.cell.PropertyValueFactory;
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
    private ComboBox<EnumKUnitBands> comboKPathUnit;

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
    private TableView<Kpoint> tableKPath;

    @FXML
    private TableColumn<Kpoint, String> columnLabel;

    @FXML
    private TableColumn<Kpoint, Double> columnKx;

    @FXML
    private TableColumn<Kpoint, Double> columnKy;

    @FXML
    private TableColumn<Kpoint, Double> columnKz;

    @FXML
    private TableColumn<Kpoint, Integer> columnNk;
    
    @FXML
    private Label statusTextField;
	
    private ObservableList<Kpoint> kpointsData;
    
	public InputBandsController (MainClass mc) {
		super(mc, EnumStep.BANDS);
		kpointsData = FXCollections.observableArrayList();
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusTextField);
		initIntegerParameterSet(textNBands, "intNBands", EnumNumCondition.positive, "Automated", checkNBands, infoNBands, null);
		setupTable();
    	
		buttonAdd.setOnAction((event) -> {	
    		Kpoint tmp = genKpointFromInput();
    		if (tmp==null) return;
			kpointsData.add(tmp);
			InputAgentBands iBands = (InputAgentBands) mainClass.projectManager.getStepAgent(enumStep);
			if (iBands==null) {statusTextField.setText("Null input bands agent.");return;}
			iBands.listKPoints.add(tmp);
			tableKPath.getSelectionModel().selectLast();
		});
		buttonEdit.setOnAction((event) -> {	
    		int selec = tableKPath.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= kpointsData.size()) {statusTextField.setText("Index out of bound to be editted.");return;}
    		statusTextField.setText("");
    		
    		Kpoint tmp = genKpointFromInput();//******is this efficient or shall we change properties of Kpoint?
    		if (tmp==null) return;
    		kpointsData.set(selec, tmp);
    		InputAgentBands iBands = (InputAgentBands) mainClass.projectManager.getStepAgent(enumStep);
			if (iBands==null) {statusTextField.setText("Null input bands agent.");return;}
			iBands.listKPoints.set(selec, tmp);
    		
			tableKPath.getSelectionModel().select(selec);
		});
		buttonDelete.setOnAction((event) -> {	
    		int selec = tableKPath.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= kpointsData.size()) {statusTextField.setText("No data is selected to be deleted.");return;}
    		statusTextField.setText("");
    		kpointsData.remove(selec);
    		InputAgentBands iBands = (InputAgentBands) mainClass.projectManager.getStepAgent(enumStep);
    		if (iBands==null) {statusTextField.setText("Null input bands agent.");return;}
    		iBands.listKPoints.remove(selec);
			tableKPath.getSelectionModel().selectNext();
		});
		buttonClearInput.setOnAction((event) -> {	
    		clearInput();
		});
    	
		setComboListener(comboKPathUnit, EnumKUnitBands.values(), "enumKUnit");
	}
	private void setupTable() {
    	//ObservableList<Atom> kpointsData =FXCollections.observableArrayList(new Atom("C",1),new Atom("H",2),new Atom("He",3));
		columnLabel.setCellValueFactory(new PropertyValueFactory<Kpoint, String>("label"));
		columnKx.setCellValueFactory(new PropertyValueFactory<Kpoint, Double>("kx"));
		columnKy.setCellValueFactory(new PropertyValueFactory<Kpoint, Double>("ky"));
		columnKz.setCellValueFactory(new PropertyValueFactory<Kpoint, Double>("kz"));
		columnNk.setCellValueFactory(new PropertyValueFactory<Kpoint, Integer>("nk"));
		
		tableKPath.setItems(kpointsData);
		
		tableKPath.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
		    if (newSelect == null) {
		    	clearInput();
		    }
		    else {
		    	textKLabel.setText(newSelect.getLabel());
		    	textKx.setText(Double.toString(newSelect.getKx()));
		    	textKy.setText(Double.toString(newSelect.getKy()));
		    	textKz.setText(Double.toString(newSelect.getKz()));
		    	textNk.setText(Integer.toString(newSelect.getNk()));
		    }
		});
    }
    private Kpoint genKpointFromInput() {
    	
		Double kx,
		ky,
		kz;
		Integer nk;
		
		try {
			kx=Double.valueOf(textKx.getText());
			ky=Double.valueOf(textKy.getText());
			kz=Double.valueOf(textKz.getText());
			nk=Integer.valueOf(textNk.getText());
			if(nk<=0) {statusTextField.setText("nk must >0.");return null;}
		}
		catch (Exception e) {
			statusTextField.setText("Not double in kx/ky/kz or not integer in nk. ");return null;
		}
		Kpoint tmp = new Kpoint(textKLabel.getText(),kx,ky,kz,nk);
		statusTextField.setText("");
		return tmp;
    }
    private void clearInput() {
    	statusTextField.setText("");
    	textKLabel.setText("");textKx.setText("");textKy.setText("");textKz.setText("");
		textKz.setText("");
		tableKPath.getSelectionModel().clearSelection();
    }
    public void loadProjectParameters() {
    	super.loadProjectParameters();
    	
    	clearInput();
    	
    	InputAgentBands iBands = (InputAgentBands) mainClass.projectManager.getStepAgent(enumStep);
		if (iBands==null) {statusTextField.setText("Null input bands agent.");return;}
    	setCombo(comboKPathUnit, iBands.enumKUnit);
    	
    	kpointsData.clear();
    	kpointsData.addAll(iBands.listKPoints);
	}

}
