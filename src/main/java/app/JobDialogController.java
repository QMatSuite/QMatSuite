package app;

import javafx.fxml.Initializable;

import java.net.URL;
import java.util.ArrayList;
import java.util.ResourceBundle;

import input.ContainerInputString;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Label;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;


public class JobDialogController implements Initializable{
	@FXML
	private BorderPane borderPaneMain;
	
	@FXML
    private Label textAreaTitle;

    @FXML
    private Button buttonStartJob;

    @FXML
    private Button buttonCancel;

    @FXML
    private VBox vboxCheckBox;

    @FXML
    private VBox vboxText;
    
    private ArrayList<Boolean> boolRunStep;
    
    private ArrayList<CheckBox> listCheckBox;
    
    private boolean boolRun=false;
    
    public JobDialogController() {
    	boolRunStep = new ArrayList<Boolean>();
    	listCheckBox = new ArrayList<CheckBox>();
    }

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		buttonStartJob.setOnAction((event) -> {
			boolRun = true;
	    	closeStage();
		});
		buttonCancel.setOnAction((event) -> {
			boolRun = false;
	    	closeStage();
		});
		
	}
	
	private void closeStage() {
		for(int i=0;i<listCheckBox.size();i++) {
			boolRunStep.set(i,listCheckBox.get(i).isSelected());
		}
        Stage stage  = (Stage) borderPaneMain.getScene().getWindow();
        stage.close();
    }
	public void initializeBoolRunStep(ArrayList<ContainerInputString> cis) {
		boolRun=false;//so that if the user clicks the cross to close the window, the job will not run
		
		boolRunStep.clear();
		vboxCheckBox.getChildren().clear();
		vboxText.getChildren().clear();
		listCheckBox.clear();
		textAreaTitle.setText(Integer.toString(cis.size())+
				(cis.size()==1? " step in total." : " steps in total."));
		for(int i=0;i<cis.size();i++) {
			boolRunStep.add(true);
			CheckBox cbNew = new CheckBox("");cbNew.setSelected(true);
			listCheckBox.add(cbNew);
			vboxCheckBox.getChildren().add(cbNew);
			vboxText.getChildren().add(new Label("Step "+Integer.toString(i+1)+": "
					+ cis.get(i).stepName.toString()
					+"("+cis.get(i).stepName.getName()+")"));
		}
		
	}
	public ArrayList<Boolean> getBoolRunStep(){
		return boolRunStep;
	}

	public boolean isBoolRun() {
		return boolRun;
	}
}
