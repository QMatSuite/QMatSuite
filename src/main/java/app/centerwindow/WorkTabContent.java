package app.centerwindow;

import java.io.IOException;
import java.util.HashMap;
import com.error.ShowAlert;
import javafx.collections.ObservableList;
import javafx.fxml.FXMLLoader;
import javafx.scene.Node;
import javafx.scene.control.Label;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import main.MainClass;

public class WorkTabContent {
	private MainClass mainClass;
	private TabPane workSpaceTabPane;//not going to change throughout the program
	private HashMap<String, Tab> projectTabDict;
	private Integer tabRowNum;
	
	private OutputViewerController contOutput;
	private HBox hboxOutput;
    
	public WorkTabContent(MainClass mainClass,TabPane workSpaceTabPane,HashMap<String, Tab> projectTabDict) {
		this.mainClass = mainClass;
		this.workSpaceTabPane = workSpaceTabPane;
		this.projectTabDict = projectTabDict;

		try {
			contOutput = new OutputViewerController(mainClass);
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/centerwindow/outputViewer.fxml"));
			fxmlLoader.setController(contOutput);
			hboxOutput = fxmlLoader.load();
		} catch (IOException e) {
			e.printStackTrace();
		}
		hboxOutput.prefWidthProperty().bind(workSpaceTabPane.widthProperty());
		hboxOutput.prefHeightProperty().bind(workSpaceTabPane.heightProperty());
	}
	public Tab setUpTabContent() {
		Tab tab = new Tab();
		VBox hbTmp = new VBox();
		ToggleButton tgButton = new ToggleButton("");tgButton.setId("idToggleGeoInOutButton");
		tgButton.setPrefWidth(150);
		
		if (mainClass.projectManager.getShow3DScene()) 
		{ tgButton.setSelected(false);tgButton.setText("Show input/output files");}
		else 
		{ tgButton.setSelected(true);tgButton.setText("Show geometry"); }
		//reversed than in projectManager
		tgButton.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) return;
			if (newValue) 
			{ tgButton.setText("Show geometry");}
			else 
			{ tgButton.setText("Show input/output files"); }
			mainClass.projectManager.setShow3DScene(!newValue);
			updateWorkScene();
		});
		
		hbTmp.getChildren().add(new HBox(tgButton,new Label("Toggle geometry and in/out files")));
		tabRowNum=2;//2 in total, including the display defined in the tab change listener
		
		tab.setContent(hbTmp);
		return tab;
	}

	public void updateWorkScene() {
		String currentPj = mainClass.projectManager.getActiveProjectName();
		if(currentPj==null) return;
		Tab newTab = this.projectTabDict.get(currentPj);
		if(newTab==null) return;
		
		VBox hbTmp = (VBox) newTab.getContent();
		//***may be unnecessary for some situations
		//remove last one. The if condition takes care of the case of first creation of a project
		if(tabRowNum==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Null of tabRowNum. Cannot load workscene.");
		}
		else {
			ObservableList<Node>  obsTmp = hbTmp.getChildren();
			if(obsTmp.size()>=tabRowNum) {obsTmp.remove(obsTmp.size()-1);}
			if(mainClass.projectManager.getShow3DScene()) {
				//add 3D view
				mainClass.projectManager.updateViewerPlot();//*******not always necessary
				WorkScene3D workScene = mainClass.projectManager.getActiveProject().getViewer3D();
				workScene.centerSubScene(workSpaceTabPane);
				AnchorPane acp = workScene.getRootPane();
				hbTmp.getChildren().add(acp);
			}
			else {
				contOutput.updateProjectFolder();
				hbTmp.getChildren().add(hboxOutput);
			}
		}
		
	}
}
