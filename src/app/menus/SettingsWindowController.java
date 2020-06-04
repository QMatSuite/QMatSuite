package app.menus;

import java.io.IOException;
import java.net.URL;
import java.util.ResourceBundle;

import com.programConst.ProgrammingConsts.settingsTags;

import app.MainLeftPaneController;
import app.input.InputGeoController;
import app.input.InputScfController;
import app.menus.settingTabs.PathsController;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.fxml.Initializable;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeView;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Priority;
import javafx.scene.layout.VBox;
import javafx.stage.Modality;
import javafx.stage.Stage;
import main.MainClass;

public class SettingsWindowController implements Initializable {

    @FXML
    private TreeView<settingsTags> treeNavigate;

    @FXML
    private Button saveButton;

    @FXML
    private Button saveCloseButton;

    @FXML
    private Button cancelButton;

    @FXML
    private BorderPane borderPaneMain;

    private TreeItem<settingsTags> treeRoot;
    
    private MainClass mainClass;
    
    private PathsController contPath;
    
    private AnchorPane panePath;
    
    public SettingsWindowController(MainClass mc) {
    	mainClass = mc;
    	
	}
    
	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		treeRoot = new TreeItem<settingsTags>(settingsTags.Settings);
		treeNavigate.setRoot(treeRoot);treeNavigate.setShowRoot(false);//treeRoot.setExpanded(true);
		//tree items
		treeRoot.getChildren().add(new TreeItem<settingsTags>(settingsTags.Paths));
		treeRoot.getChildren().add(new TreeItem<settingsTags>(settingsTags.Viewer3D));
		
		try {
			contPath = new PathsController(mainClass);
			FXMLLoader fxmlLoader1 = new FXMLLoader(this.getClass().getResource("settingTabs/paths.fxml"));
			fxmlLoader1.setController(contPath);
			panePath = fxmlLoader1.load();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		treeNavigate.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) -> {
			if (newValue==null || newValue.getValue()==null) return;
			if (mainClass==null) return;
			
			
			switch(newValue.getValue()) {
				case Paths:
					borderPaneMain.setCenter(panePath);
					BorderPane.setAlignment(panePath, Pos.TOP_LEFT);
					//panePath.setStyle("-fx-background-color: blue");
					contPath.loadPaths();
					break;
				case Viewer3D:
					break;
				default:
			}
		});

	    saveButton.setOnAction((event) -> {
	    	saveChanges();
		});
	    saveCloseButton.setOnAction((event) -> {
	    	saveChanges();
	    	closeStage();
		});
	    cancelButton.setOnAction((event) -> {
	    	cancelChanges();
		});
	}
	private void cancelChanges() {
		
	}
	private void saveChanges() {
		
	}
	private void closeStage() {
        Stage stage  = (Stage) borderPaneMain.getScene().getWindow();
        stage.close();
    }

}