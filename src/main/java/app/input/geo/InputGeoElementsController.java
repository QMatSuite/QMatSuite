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

package app.input.geo;

import java.io.File;
import java.net.URL;
import java.util.ResourceBundle;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import main.MainClass;
import agent.InputAgentGeo;
import app.input.InputController;
import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.consts.Constants.EnumStep;
import com.pseudopot.EnumPseudoPotLib;
import com.pseudopot.PSLibraryClass;
import com.pseudopot.PseudoDojoClass;
import com.pseudopot.SSSPClass;

public class InputGeoElementsController extends InputController{

	@FXML private VBox rootVbox;
	
	@FXML private Button defButton;

	@FXML private TableView<Element> elementTable;
    
    @FXML private TableColumn<Element, Integer> indexColumn;
    
    @FXML private TableColumn<Element, Double> massColumn;
    
    @FXML private TableColumn<Element, String> nameColumn;
    
    @FXML private TableColumn<Element, String> pseudoColumn;

    @FXML
    private Label ppTypePoint,
    xcFuncPoint,
    ecutwfcPoint,
    ecutrhoPoint,
    labelPathPseudoLib;

    @FXML
    private Label ppTypeLabel,
    xcFuncLabel,
    ecutwfcLabel,
    ecutrhoLabel,
    relavLabel,
    relavPoint,
    fullPathLabel,
    labelPrecision;

	
    @FXML private ComboBox<EnumFunctional> comboFunctional;
    
    @FXML private ComboBox<EnumPP> comboPP;
    
    @FXML private ComboBox<EnumPseudoPotLib> comboLib;
    
    @FXML private ComboBox<String> comboPrec;
    
    @FXML private CheckBox checkRelativ,
    resetCheck;
    
    private ObservableList<Element> elemData;
	
    private PseudoDojoClass pdClass;
    
    private SSSPClass ssspClass;
    
    private PSLibraryClass psLibClass;
    
	public InputGeoElementsController(MainClass mc) {
		super(mc, EnumStep.GEO);
		elemData = FXCollections.observableArrayList();
		pdClass = new PseudoDojoClass();
		ssspClass = new SSSPClass();
		psLibClass = new PSLibraryClass();
	}
    
    @Override
    public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    private void refreshLibList() {
    	ObservableList<EnumPseudoPotLib> typeLib = FXCollections.observableArrayList(EnumPseudoPotLib.values());
    	if(!pdClass.checkLibraryExistence()) {typeLib.remove(EnumPseudoPotLib.PSEUDODOJO);}
    	if(!ssspClass.checkLibraryExistence()) {typeLib.remove(EnumPseudoPotLib.SSSP);}
    	if(!psLibClass.checkLibraryExistence()) {typeLib.remove(EnumPseudoPotLib.PSLIBRARY);}
    	comboLib.setItems(typeLib);
    }
    public void initialize() {
    	//pseudoPot library
    	
    	refreshLibList();
    	
    	labelPrecision.setText("Precision");
    	comboLib.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
    		ObservableList<EnumFunctional> typeFunc;
    		ObservableList<EnumPP> typePP;
    		ObservableList<String> typePrec;
    		boolean bl;
    		
    		if(newSelect==null) return;
    		if(EnumPseudoPotLib.SSSP.equals(newSelect)) {
    			typeFunc = FXCollections.observableArrayList(ssspClass.getFunctionalList());
    			typePP = FXCollections.observableArrayList(ssspClass.getPpList());
    			typePrec = FXCollections.observableArrayList(ssspClass.getPrecisionList());
    			bl = ssspClass.getFullRelativSupport();
    			labelPrecision.setText("Precision");
    		}
    		else if(EnumPseudoPotLib.PSEUDODOJO.equals(newSelect)) {
    			typeFunc = FXCollections.observableArrayList(pdClass.getFunctionalList());
    			typePP = FXCollections.observableArrayList(pdClass.getPpList());
    			typePrec = FXCollections.observableArrayList(pdClass.getPrecisionList());
    			bl = pdClass.getFullRelativSupport();
    			labelPrecision.setText("Precision");
    		}
    		else if(EnumPseudoPotLib.PSLIBRARY.equals(newSelect)){
    			typeFunc = FXCollections.observableArrayList(psLibClass.getFunctionalList());
    			typePP = FXCollections.observableArrayList(psLibClass.getPpList());
    			typePrec = FXCollections.observableArrayList(psLibClass.getPrecisionList());
    			bl = psLibClass.getFullRelativSupport();
    			labelPrecision.setText("Cutoff (pref.)");
    		}
    		else {
    			return;
    		}
    		
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia==null) return; 
			
			ia.typeLib=newSelect;
			
			//a bit complicated because needs to consider:
			//loading, don't want to overwrite things
			//user change library combobox
			//don't want to have empty selection
			EnumFunctional efTmp = ia.typeFunctional;
        	comboFunctional.setItems(typeFunc);comboFunctional.setDisable(typeFunc.isEmpty());
        	if(typeFunc.isEmpty()) {comboFunctional.getSelectionModel().clearSelection();}
        	else if (efTmp!=null && typeFunc.contains(efTmp)) {comboFunctional.getSelectionModel().select(efTmp);}
        	else {comboFunctional.getSelectionModel().select(0);}
        	
        	EnumPP epTmp = ia.typePP;
        	comboPP.setItems(typePP);comboPP.setDisable(typePP.isEmpty());
        	if(typePP.isEmpty()) {comboPP.getSelectionModel().clearSelection();}
        	else if (epTmp!=null && typePP.contains(epTmp)) {comboPP.getSelectionModel().select(epTmp);}
        	else {comboPP.getSelectionModel().select(0);}

        	Integer intTmp = ia.typePrec;
        	comboPrec.setItems(typePrec);comboPrec.setDisable(typePrec.isEmpty());
        	if(typePrec.isEmpty()) {comboPrec.getSelectionModel().clearSelection();}
        	else if (intTmp!=null && typePrec.size()>intTmp) {comboPrec.getSelectionModel().select(intTmp);}
        	else {comboPrec.getSelectionModel().select(0);}
        	

        	checkRelativ.setDisable(!bl);
        	if(!bl && checkRelativ.isSelected()) {checkRelativ.setSelected(false);}
        	
        	//*******very inefficient because will run multiple times
			updatePseudoElementList();
		});
    	//default use SSSP library, not necessary here
    	//comboLib.getSelectionModel().select(EnumPseudoPotLib.SSSP);
    	
    	
    	//functional type
    	comboFunctional.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typeFunctional=comboFunctional.getValue();
			if (comboFunctional.getValue()!=null) {
				updatePseudoElementList();
			}
		});
    	//pp type
    	comboPP.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typePP=comboPP.getValue();
			if (comboPP.getValue()!=null) {
				updatePseudoElementList();
			}
			
		});
    	//precision type
    	comboPrec.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typePrec=comboPrec.getSelectionModel().getSelectedIndex();
			if (comboPrec.getValue()!=null) {
				updatePseudoElementList();
			}
		});
    	//full relativistic
    	checkRelativ.selectedProperty().addListener((obs, oldSelect, newSelect) -> {
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.isRelativ.setValue(newSelect);
			updatePseudoElementList();
		    //if (newSelect) comboPP.getSelectionModel().select(EnumPP.USPP);//no need to change ia.typePP explicitly
		});
    	//reset to default: SSSP, Efficiency
    	resetCheck.selectedProperty().addListener((obs, oldSelect, newSelect) -> {
    		if (newSelect!=null && newSelect) {
    			comboLib.getSelectionModel().select(EnumPseudoPotLib.SSSP);comboLib.setDisable(true);
    			comboPrec.getSelectionModel().select(0);comboPrec.setDisable(true);
    			comboFunctional.getSelectionModel().select(0);comboFunctional.setDisable(true);
			}
    		else {comboLib.setDisable(false);comboPrec.setDisable(false);comboFunctional.setDisable(false);}
			updatePseudoElementList();
		});
    	//setup element table
    	setupTable();
    }
    public void updatePseudoElementList() {
    	//********reconsider the efficiency!
    	if(mainClass.projectManager.getPseudoLibPath()!=null) {
    		labelPathPseudoLib.setText(mainClass.projectManager.getPseudoLibPath());}//may be not necessary
    	refreshLibList();
    	
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
    	
    	if(iGeo.elemListAll==null || iGeo.elemListAll.isEmpty() || elemData==null || elemData.isEmpty()) return;
    	
    	EnumPseudoPotLib eppl = comboLib.getSelectionModel().getSelectedItem();
    	
    	if(eppl==null) return;
    	switch(eppl) {
    		case SSSP:
    			ssspClass.setPrecString(comboPrec.getSelectionModel().getSelectedItem());
    			
    			break;
    		case PSEUDODOJO:
    			pdClass.setRelativ(checkRelativ.isSelected());
    			pdClass.setTypeFunctional(comboFunctional.getSelectionModel().getSelectedItem());
    			pdClass.setPrecString(comboPrec.getSelectionModel().getSelectedItem());
    			
    			break;
    		case PSLIBRARY:
    			psLibClass.setRelativ(checkRelativ.isSelected());
    			psLibClass.setTypeFunctional(comboFunctional.getSelectionModel().getSelectedItem());
    			psLibClass.setTypePP(comboPP.getSelectionModel().getSelectedItem());
    			psLibClass.setPrecString(comboPrec.getSelectionModel().getSelectedItem());
    			
    			break;
    		default: return;
    	}
    	
    	String libFolderPath=null;
    	if(iGeo.elemListAll.size()!=elemData.size()) {
    		Alert alert = new Alert(AlertType.INFORMATION);
	    	alert.setTitle("Warning");
	    	alert.setContentText("The size of elemData and elemListAll is not equal! Should not happen usually, but don't worry though...");
	    	alert.showAndWait();
	    	
	    	elemData.clear();
	    	elemData.addAll(iGeo.elemListAll);
    	}
    	for (int i=0;i<iGeo.elemListAll.size();i++) {
			Element ele1 = iGeo.elemListAll.get(i);
			Element ele2 = elemData.get(i);
			if(ele1==null || ele2==null) continue;
			String pseudoPotFile;
    		switch(eppl) {
	    		case SSSP:
	    			pseudoPotFile=ssspClass.getFile(ele1.getAtomSpecies().toString());
		    		if(libFolderPath==null) {libFolderPath=ssspClass.getFolder(ele1.getAtomSpecies().toString());}
		    		break;
	    		case PSEUDODOJO:
	    			pseudoPotFile=pdClass.getFile(ele1.getAtomSpecies().toString());
		    		if(libFolderPath==null) {libFolderPath=pdClass.getFolder(ele1.getAtomSpecies().toString());}
		    		break;
	    		case PSLIBRARY:
	    			pseudoPotFile=psLibClass.getFile(ele1.getAtomSpecies().toString());
	    			//ShowAlert.showAlert(AlertType.INFORMATION, "debug", pseudoPotFile);
		    		if(libFolderPath==null) {libFolderPath=psLibClass.getFolder(ele1.getAtomSpecies().toString());}
		    		break;
	    		default: 
	    			return;
    		}
    		
    		ele1.setPseudoPotFile(pseudoPotFile);
    		ele2.setPseudoPotFile(pseudoPotFile);
    		boolean bl = existPseudoFile(pseudoPotFile);
    		ele1.setPseudoValid(bl);
    		ele2.setPseudoValid(bl);
    		elemData.set(i, ele2);
    		
    		if(mainClass.projectManager.getPseudoLibPath()!=null && libFolderPath!=null) {
    			iGeo.pseudodir = mainClass.projectManager.getPseudoLibPath()+File.separator+libFolderPath;
	    	}
		}
    	
    	updatePseudoInfo();
    }
    private String getDisplayedName(String fullPath) {
    	if(fullPath==null) return null;
    	int ind1 = fullPath.lastIndexOf(File.separator);
    	if(ind1==-1) return null;//no separator detected
    	int ind2 = fullPath.lastIndexOf(File.separator,Math.max(ind1-1, 0));
    	if(ind2==-1) return fullPath;
    	else {return fullPath.substring(ind2+1);}//ind2<=ind1-1 -> ind2+1<=ind1<fullPath.size() -> safe
    }
    private void updatePseudoInfo() {
    	Element el = elementTable.getSelectionModel().getSelectedItem();
    	if(el==null) {
    		ecutwfcLabel.setText("");ecutrhoLabel.setText("");ppTypeLabel.setText("");xcFuncLabel.setText("");
    		relavLabel.setText("");fullPathLabel.setText("");
    		return;}
    	
    	String pseudoLibRoot = mainClass.projectManager.getPseudoLibPath();
    	if(pseudoLibRoot==null) {fullPathLabel.setText(el.getPseudoPotFile());}
    	else {fullPathLabel.setText(pseudoLibRoot+File.separator+el.getPseudoPotFile());}
    	
    	String elemSpec = el.getAtomSpecies().toString();
    	if(elemSpec==null || elemSpec.isEmpty()) return;
    	
    	EnumPseudoPotLib eppl = comboLib.getSelectionModel().getSelectedItem();
    	if(eppl==null) return;
    	
    	Double ecutwfc,
    	dual;
    	
    	String ppType, 
    	functionalType;
    	
    	switch(eppl) {
			case SSSP:
				ecutwfc = ssspClass.getEcutWfc(elemSpec);
				dual = ssspClass.getDual(elemSpec);
				ppType = ssspClass.getPpType(elemSpec);
				functionalType = ssspClass.getFunctionalType(elemSpec);
				break;
			case PSEUDODOJO:
				ecutwfc = pdClass.getEcutWfc(elemSpec);
				dual = pdClass.getDual(elemSpec);
				ppType = pdClass.getPpType(elemSpec);
				functionalType = pdClass.getFunctionalType(elemSpec);
				break;
			case PSLIBRARY:
				ecutwfc = psLibClass.getEcutWfc(elemSpec);
				dual = psLibClass.getDual(elemSpec);
				ppType = psLibClass.getPpType(elemSpec);
				functionalType = psLibClass.getFunctionalType(elemSpec);
				break;
			default: return;
    	}
    	if(ecutwfc!=null) {ecutwfcLabel.setText(ecutwfc.toString()+" Ry");}else {ecutwfcLabel.setText("");}
    	if(dual!=null && ecutwfc!=null) {dual*=ecutwfc;ecutrhoLabel.setText(dual.toString()+" Ry");}else {ecutrhoLabel.setText("");}
    	if(ppType!=null && !ppType.isEmpty()) {ppTypeLabel.setText(ppType);}else {ppTypeLabel.setText("");}
    	if(functionalType!=null && !functionalType.isEmpty()) {xcFuncLabel.setText(functionalType);}else {xcFuncLabel.setText("");}
    	relavLabel.setText(checkRelativ.isSelected()?"Full relativistic":"Scalar relativistic");
    }
    private void setupTable() {
    	indexColumn.setCellValueFactory(new PropertyValueFactory<Element, Integer>("index"));
    	indexColumn.setCellFactory(col -> {
		    TableCell<Element, Integer> cell = new TableCell<>();
		    cell.textProperty().bind(Bindings.createStringBinding(() -> {
		        if (cell.isEmpty()) {
		            return null ;
		        } else {
		            return Integer.toString(cell.getIndex()+1);
		        }
		    }, cell.emptyProperty(), cell.indexProperty()));
		    return cell ;
		});
    	nameColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("atomSpecies"));
    	massColumn.setCellValueFactory(new PropertyValueFactory<Element, Double>("atomMass"));
    	pseudoColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("pseudoPotFile"));
    	pseudoColumn.setCellFactory(column -> {
		    return new TableCell<Element, String>() {
		        @Override
		        protected void updateItem(String item, boolean empty) {
		            super.updateItem(item, empty);
		            if (empty) {setStyle("");setText(null);return;}
		            if (item == null || item.isEmpty()) {
		                setText(null);
		                setStyle("-fx-background-color: red");
		            } else {

		                setText(getDisplayedName(item));
		                
		                //***not efficient. Runs twice
		                boolean bl = existPseudoFile(item);
		                
		                if (!bl) {
		                    setTextFill(Color.CHOCOLATE);
		                    setStyle("-fx-background-color: red");
		                } else {
		                    setTextFill(Color.BLACK);
		                    setStyle("-fx-background-color: lightgreen");
		                }
		            }
		        }
		    };
		});
    	elementTable.setItems(elemData);
		
    	elementTable.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
    		updatePseudoInfo();
		});
    }
    private boolean existPseudoFile(String fileName) {
		String pseudoLibRoot = mainClass.projectManager.getPseudoLibPath();
		if(pseudoLibRoot==null) return false;
		File pseudoFile = new File(pseudoLibRoot+File.separator+fileName);
		return pseudoFile.canRead();
	}
    public void loadProjectParameters() {
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (iGeo==null) return;
		iGeo.updateElemListAll();//from atom generate elements table. Necessary if previous ElementList is loaded but not correctly generated
		
		elemData.clear();
		elemData.addAll(iGeo.elemListAll);
		
		if (iGeo.typeLib==null) {comboLib.getSelectionModel().clearSelection();}
		else {comboLib.getSelectionModel().select(iGeo.typeLib);}
		//*************not efficient, run twice possible
		if (iGeo.typeFunctional==null) {comboFunctional.getSelectionModel().clearSelection();}
		else {comboFunctional.getSelectionModel().select(iGeo.typeFunctional);}
		if (iGeo.typePP==null) {comboPP.getSelectionModel().clearSelection();}
		else {comboPP.getSelectionModel().select(iGeo.typePP);}
		if (iGeo.typePrec==null) {comboPrec.getSelectionModel().clearSelection();}
		else {comboPrec.getSelectionModel().select(iGeo.typePrec);}
		checkRelativ.setSelected(iGeo.isRelativ.getValue());//should not be null!
		
		updatePseudoElementList();
		
		if(mainClass.projectManager.getPseudoLibPath()!=null) {labelPathPseudoLib.setText(mainClass.projectManager.getPseudoLibPath());}
    }
}
