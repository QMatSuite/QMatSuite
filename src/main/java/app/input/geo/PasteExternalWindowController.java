package app.input.geo;

import java.net.URL;
import java.util.ArrayList;
import java.util.ResourceBundle;

import agent.InputAgentGeo;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.TextArea;
import javafx.scene.layout.BorderPane;
import javafx.stage.Stage;
import main.MainClass;

public class PasteExternalWindowController implements Initializable{
	@FXML
    private BorderPane borderPaneMain;

    @FXML
    private Button buttonSave;

    @FXML
    private Button buttonCancel;

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
    private Label labelStatus;
    
    private MainClass mainClass;
    
    private boolean boolSave = false;
    
    private String textInput;
    
    private InputAgentGeo iGeoPaste;
    
    public PasteExternalWindowController(MainClass mc) {
    	mainClass = mc;
	}
    public void initializeConversion() {
    	iGeoPaste = new InputAgentGeo();//***check possibility of ram leak
    	textInput = "";
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
		textAreaInput.textProperty().addListener((obs,oldText,newText)->{
			if(!checkText(newText)) {return;}
			updatePreview();
		});
	}
	private boolean checkText(String textInput) {
		if(textInput==null || textInput.isEmpty()) {return false;}
//		if(textInput.toUpperCase().contains("ATOMIC_POSITIONS") || textInput.toUpperCase().contains("CELL_PARAMETERS")) {
//			
//		}
//		else {
//			return false;
//		}	
		if(!this.iGeoPaste.convertInfoFromInput(textInput)) {return false;}
		return true;
	}
	private void updatePreview() {
		
		String msg = "Information read from the input:\n";
		
		msg += this.iGeoPaste.genAgentSummary();
		
		//update preview
		textAreaPreview.setText(msg);
	}
	private void closeStage() {
        Stage stage  = (Stage) this.borderPaneMain.getScene().getWindow();
        stage.close();
    }
	public boolean isBoolSave() {
		return boolSave;
	}
}
