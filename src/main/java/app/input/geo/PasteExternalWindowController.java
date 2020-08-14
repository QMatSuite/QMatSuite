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
package app.input.geo;

import java.net.URL;
import java.util.ResourceBundle;

import com.consts.Constants.EnumStep;

import agent.InputAgentBands;
import agent.InputAgentGeo;
import agent.InputAgentPhonon;
import core.agent.InputAgent;
import core.com.error.ShowAlert;
import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.TextArea;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.layout.BorderPane;
import javafx.stage.Stage;

public class PasteExternalWindowController implements Initializable{
	@FXML
    private BorderPane borderPaneMain;

    @FXML
    private Button buttonCancel,
    buttonSave,
    buttonClearAll;

    @FXML
    private TabPane tabPanePaste;

    @FXML
    private Tab tabInput;

    @FXML
    private TextArea textAreaInput;

    @FXML
    private Tab tabPreview;

    @FXML
    private TextArea textAreaPreview;
    
    @FXML
    private Label labelStatus,
    labelTitle;
    
    private MainClass mainClass;
    
    private boolean boolSave = false;
    
    private InputAgent iAgent = null;//***check possibility of ram leak
    
    private final EnumStep enumStep; 
    
    public PasteExternalWindowController(MainClass mc, EnumStep es) {
    	mainClass = mc;
    	enumStep = es;
    	if(es==null) {
    		ShowAlert.showAlert(AlertType.ERROR, "Error", "EnumStep is null in class PasteExternalWindowController. Check programming.");
    	}
	}
    public InputAgent getGeoAgent() {
    	return iAgent;
    }
    public void initializeConversion() {
    	switch(enumStep) {
    		case GEO:
    			labelTitle.setText("Paste the atomic positions/cell parameters below:");
    			iAgent = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent().deepCopy();//should be safe to assume geoAgent exists
    			break;
    		case BANDS:
    			labelTitle.setText("Paste the k-points below:");
    			iAgent = (InputAgentBands) mainClass.projectManager.getStepAgent(enumStep).deepCopy();//should be safe to assume not null
    			break;
    		case PH:
    			labelTitle.setText("Paste the q-points below:");
    			iAgent = (InputAgentPhonon) mainClass.projectManager.getStepAgent(enumStep).deepCopy();//should be safe to assume not null
    			break;
    		default:
    			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "EnumStep "+enumStep+" unsupported in PasteExternalWindowController.");
    			break;
    	}
    	
    	textAreaPreview.setText("Nothing recognized yet.");
    	textAreaInput.setText("");
    	boolSave = false;
    }
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		labelStatus.setText("");
		textAreaPreview.setEditable(false);
		buttonSave.setOnAction((event) -> {	
			boolSave = true;
			closeStage();
		});
		buttonCancel.setOnAction((event) -> {	
			boolSave = false;
			closeStage();
		});
		buttonClearAll.setOnAction((event) -> {	
			iAgent = new InputAgentGeo();
			textAreaPreview.setText("Everything cleared.");
	    	textAreaInput.setText("");
		});
		textAreaInput.textProperty().addListener((obs,oldText,newText)->{
			if(!checkText(newText)) {return;}
			updatePreview();
		});
	}
	private boolean checkText(String textInput) {
		if(textInput==null || textInput.isEmpty()) {return false;}

		return this.iAgent.convertInfoFromInput(textInput);
	}
	private void updatePreview() {
		
		String msg = "Information read from the input:\n";
		
		msg += this.iAgent.genAgentSummary();
		
		//update preview
		textAreaPreview.setText(msg);
	}
	private void closeStage() {
		textAreaInput.setText("");
		textAreaPreview.setText("");
        Stage stage  = (Stage) this.borderPaneMain.getScene().getWindow();
        stage.close();
    }
	public boolean isBoolSave() {
		return boolSave;
	}
}
